import aiohttp
import asyncio
from lxml import html
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import TextMessageEventContent, MessageType, Format
from mautrix.util.config import BaseProxyConfig, ConfigUpdateHelper
from .resources import languages
from typing import Type


class Config(BaseProxyConfig):
    def do_update(self, helper: ConfigUpdateHelper) -> None:
        helper.copy("region")
        helper.copy("safesearch")


class DdgBot(Plugin):
    async def start(self) -> None:
        await super().start()
        self.config.load_and_update()

    @command.new(name="ddg", aliases=["duckduckgo"], help="Get the most relevant result from DuckDuckGo Web Search")
    @command.argument("query", pass_raw=True, required=True)
    async def search(self, evt: MessageEvent, query: str) -> None:
        await evt.mark_read()
        query = query.strip().replace("!", "").replace("\\", "")
        if not query:
            await evt.reply("> **Usage:** !ddg <query>")
            return
        # Duckduckgo doesn't accept queries longer than 500 characters
        if len(query) >= 500:
            await evt.reply("> Query is too long.")

        message = None
        response = await self.get_result(query)
        if response:
            message = await asyncio.get_event_loop().run_in_executor(None, self.prepare_message, response)
        if not message:
            await evt.reply(f"> Failed to find results for *{query}*")
            return
        await evt.reply(message)

    async def get_result(self, query: str) -> str:
        """
        Get results from DuckDuckGo.
        :param query: search query
        :return: results HTML page
        """
        headers = {
            "Sec-GPC": "1",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "en,en-US;q=0.5",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:140.0) Gecko/20100101 Firefox/140.0",
            "referer": "https://duckduckgo.com/"
        }
        vqd = await self.get_vqd(query)
        if not vqd:
            self.log.error(f"Failed to obtain vqd token")
            return ""

        data = {
            "q": query,
            "vqd": vqd,
            "kd": "-1",  # Redirect off
            "k1": "-1",  # Ads: 1 on, -1 off
            "kl": self.get_region(),  # Region: wt-wt for no region
            "p": self.get_safesearch()  # Safe search
        }
        url = "https://lite.duckduckgo.com/lite/search"
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            response = await self.http.post(url, headers=headers, data=data, timeout=timeout, raise_for_status=True)
            res_text = await response.text()
        except aiohttp.ClientError as e:
            self.log.error(f"Connection failed: {e}")
            return ""
        return res_text

    async def get_vqd(self, query: str) -> str:
        """
        Get special search token required by DuckDuckGo
        :param query: search query
        :return: vqd token
        """
        url = "https://duckduckgo.com/"
        # Make a request to above URL, and parse out the 'vqd'
        # This is a special token, which should be used in the subsequent request
        params = {
            'q': query
        }
        timeout = aiohttp.ClientTimeout(total=20)
        try:
            response = await self.http.get(url, params=params, timeout=timeout, raise_for_status=True)
            res_text = await response.text()
            for c1, c1_len, c2 in (("vqd=\"", 5, "\""), ("vqd=", 4, "&"), ("vqd='", 5, "'")):
                try:
                    start = res_text.index(c1) + c1_len
                    end = res_text.index(c2, start)
                    token = res_text[start:end]
                    return token
                except ValueError:
                    self.log.error(f"Token parsing failed")
                    return ""
        except aiohttp.ClientError as e:
            self.log.error(f"Failed to obtain token. Connection failed: {e}")
            return ""

    def prepare_message(self, text: str) -> TextMessageEventContent | None:
        """
        Prepare message by parsing HTML content of results page
        :param text: HTML content of results page
        :return: message ready to be sent to the user
        """
        page = html.fromstring(text)
        if page is None:
            return None
        link = page.xpath("//a[@class='result-link']")
        link = link[0] if link else None
        if link is None:
            return None
        link_text = link.text_content()
        link = link.xpath("@href")
        link = link[0] if link else ""
        # When there are no results, DDG returns a link to Google Search with EOT title
        if link_text == "EOF" and link.startswith(("http://www.google.com/search", "https://www.google.com/search")):
            return None
        link_snippet = page.xpath("//td[@class='result-snippet']")
        link_snippet = link_snippet[0].text_content().strip() if link_snippet else ""

        body = f"> **[{link_text}]({link})**  \n"
        html_msg = (
            f"<blockquote>"
            f"<a href=\"{link}\">"
            f"<b>{link_text}</b>"
            f"</a>"
        )
        if link_snippet:
            body += f"> {link_snippet}  \n"
            html_msg += f"<p>{link_snippet}</p>"
        body += f"> > **Results from DuckDuckGo**"
        html_msg += (
            f"<p><b><sub>Results from DuckDuckGo</sub></b></p>"
            f"</blockquote>"
        )
        return TextMessageEventContent(
            msgtype=MessageType.NOTICE,
            format=Format.HTML,
            body=body,
            formatted_body=html_msg)

    def get_safesearch(self) -> str:
        """
        Get safe search filter status from config
        :return: Value corresponding to safe search status
        """
        safesearch_base = {
            "on": "-1",
            "off": "1"
        }
        return safesearch_base.get(self.config.get("safesearch", "on"), safesearch_base["on"])

    def get_region(self) -> str:
        """
        Get search region from config
        :return: Search region
        """
        region = self.config.get("region", "wt-wt").lower()
        if region in languages.regions:
            return region
        return "wt-wt"

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        return Config
