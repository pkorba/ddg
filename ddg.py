import aiohttp
from maubot import Plugin, MessageEvent
from maubot.handlers import command
from mautrix.types import TextMessageEventContent, MessageType, Format
from bs4 import BeautifulSoup


class DdgBot(Plugin):
    @command.new(name="s", help="Get the most relevant result from DuckDuckGo Web Search")
    @command.argument("query", pass_raw=True, required=True)
    async def search(self, evt: MessageEvent, query: str) -> None:
        await evt.mark_read()
        query = query.strip()
        if not query:
            await evt.respond("Usage: !s <query>")
            return
        response = await self.get_result(query)
        message = await self.prepare_message(response)
        if not message:
            await evt.reply(f"Failed to find results for *{query}*")
            return
        await evt.reply(message)

    async def get_result(self, query: str) -> str:
        headers = {
            "Sec-GPC": "1",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "pl,en-US;q=0.7,en;q=0.3",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0"
        }
        params = {
            "q": query,
            "kd": "-1",  # Redirect off
            "k1": "-1",  # Ads: 1 on, -1 off
            "kl": "wt-wt"  # Region: wt-wt for no region
        }
        url = f"https://lite.duckduckgo.com/lite/"
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            response = await self.http.get(url, headers=headers, params=params, timeout=timeout, raise_for_status=True)
            res_text = await response.text()
        except aiohttp.ClientError as e:
            self.log.error(f"Connection failed: {e}")
            return ""
        return res_text

    async def prepare_message(self, text: str) -> TextMessageEventContent | None:
        soup = BeautifulSoup(text, "html.parser")
        if not soup:
            self.log.error("Failed to parse the source.")
            return None
        link = soup.find("a", class_="result-link")
        if not link:
            self.log.error("Failed to find the link.")
            return None
        # When there are no results, DDG returns a link to Google Search with EOT title
        if link.text == "EOF" and (link["href"].startswith("http://www.google.com/search") or link["href"].startswith("https://www.google.com/search")):
            return None
        link_snippet = soup.find("td", class_="result-snippet")
        link_snippet_text = link_snippet.text.strip() if link_snippet else ""

        body = f"> **[{link.text}]({link["href"]})**  \n"
        html = (
            f"<blockquote>"
            f"<a href=\"{link["href"]}\">"
            f"<b>{link.text}</b>"
            f"</a>"
        )

        if link_snippet_text:
            body += f"> {link_snippet_text}  \n"
            html += f"<p>{link_snippet_text}</p>"

        body += f"> > **Results from DuckDuckGo**"
        html += (
            f"<p><b><sub>Results from DuckDuckGo</sub></b></p>"
            f"</blockquote>"
        )

        return TextMessageEventContent(
            msgtype=MessageType.NOTICE,
            format=Format.HTML,
            body=body,
            formatted_body=html)
