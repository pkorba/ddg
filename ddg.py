import aiohttp
from maubot import Plugin, MessageEvent
from maubot.handlers import command


class DdgBot(Plugin):
    @command.new(name="s", help="DuckDuckGo Search")
    @command.argument("query", pass_raw=True, required=True)
    async def search(self, evt: MessageEvent, query: str) -> None:
        await evt.mark_read()
        query = query.strip()
        if not query:
            await evt.respond("Usage: !s <query>")
            return
        url = await self.web_search(query)
        if not url:
            await evt.reply(f"Failed to find results for {query}")
            return
        await evt.reply(f"{url}")

    async def web_search(self, query: str) -> str:
        url = f"https://lite.duckduckgo.com/lite/?q=\\+{query}"
        try:
            timeout = aiohttp.ClientTimeout(total=7)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(url, allow_redirects=True) as response:
                    result_url = str(response.url)
                    if "duckduckgo.com" in result_url:
                        return ""
                    return result_url
        except aiohttp.ClientError as e:
            self.log.error(f"Connection failed: {url}: {e}")
            return ""
