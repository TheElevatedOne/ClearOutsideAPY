"""Cloudflare Worker entrypoint: JSON API over clearoutside.com forecasts."""

from js import caches
from workers import Response, WorkerEntrypoint

from clear_outside_apy.api import DEFAULT_CACHE_TTL, handle


def _cache_ttl(env) -> int:
    try:
        return int(getattr(env, "CACHE_TTL", DEFAULT_CACHE_TTL))
    except (TypeError, ValueError):
        return DEFAULT_CACHE_TTL


class Default(WorkerEntrypoint):
    async def fetch(self, request):
        cache_ttl = _cache_ttl(self.env)
        # Parsing costs ~20 ms of CPU under Pyodide, so serve repeats from the
        # edge cache. (The Cache API only works on custom domains / routes;
        # on *.workers.dev it is a no-op.)
        use_cache = request.method == "GET" and cache_ttl > 0
        if use_cache:
            hit = await caches.default.match(request.url)
            if hit:
                return Response(hit)

        status, body, headers = await handle(
            request.method, request.url, cache_ttl=cache_ttl
        )
        response = Response(body, status=status, headers=headers)
        if use_cache and status == 200:
            self.ctx.waitUntil(caches.default.put(request.url, response.js_object.clone()))
        return response
