import aiohttp
from maubot import Plugin, MessageEvent
from maubot.handlers import command


class DdgBot(Plugin):
    @command.new(name="s", help="Get the most relevant result from DuckDuckGo Web Search")
    @command.argument("query", pass_raw=True, required=True)
    async def search(self, evt: MessageEvent, query: str) -> None:
        await evt.mark_read()
        query = query.strip()
        if not query:
            await evt.respond("Usage: !s <query>")
            return
        url = await self.web_search(query)
        if not url:
            await evt.reply(f"Failed to find results for *{query}*")
            return
        await evt.reply(f"{url}")

    async def web_search(self, query: str) -> str:
        headers = {
            "Sec-GPC": "1",
            "accept-encoding": "gzip, deflate, br, zstd",
            "accept-language": "pl,en-US;q=0.7,en;q=0.3",
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"
        }
        url = f"https://lite.duckduckgo.com/lite/?q=\\+{query}"
        try:
            timeout = aiohttp.ClientTimeout(total=20)
            response = await self.http.get(url, headers=headers, allow_redirects=True, timeout=timeout, raise_for_status=True)
            result = str(response.url)
            if "duckduckgo.com" not in result:
                return result
        except aiohttp.ClientError as e:
            self.log.error(f"Connection failed: {e}")
        return ""
