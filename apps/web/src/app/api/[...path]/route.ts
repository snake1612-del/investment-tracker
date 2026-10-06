// Resolve the deployment-local service binding at request time, never at build time.
export const runtime = "nodejs";
export const dynamic = "force-dynamic";

async function proxy(request: Request): Promise<Response> {
  const base =
    process.env.API_URL ??
    (process.env.VERCEL ? undefined : "http://127.0.0.1:8000");
  if (!base) {
    return Response.json(
      { detail: "API service binding unavailable" },
      { status: 503 },
    );
  }
  const source = new URL(request.url);
  const target = new URL(base.endsWith("/") ? base : `${base}/`);
  const servicePath = target.pathname;
  target.pathname += source.pathname.slice("/api/".length);
  target.search = source.search;
  const headers = new Headers();
  for (const name of ["accept", "content-type"]) {
    const value = request.headers.get(name);
    if (value) headers.set(name, value);
  }
  try {
    const response = await fetch(target, {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
    });
    const outgoing = new Headers({ "cache-control": "no-store" });
    for (const name of ["content-type"]) {
      const value = response.headers.get(name);
      if (value) outgoing.set(name, value);
    }
    const location = response.headers.get("location");
    if (location) {
      const redirected = new URL(location, target);
      if (
        redirected.origin !== target.origin ||
        !redirected.pathname.startsWith(servicePath)
      ) {
        throw new Error("Unexpected service redirect");
      }
      // Keep private binding URLs out of browser-visible redirect headers.
      outgoing.set(
        "location",
        `${source.origin}/api/${redirected.pathname.slice(servicePath.length)}${redirected.search}`,
      );
    }
    return new Response(response.body, {
      status: response.status,
      headers: outgoing,
    });
  } catch {
    return Response.json(
      { detail: "API service unavailable" },
      { status: 502 },
    );
  }
}

export {
  proxy as GET,
  proxy as POST,
  proxy as PUT,
  proxy as DELETE,
  proxy as PATCH,
  proxy as HEAD,
};
