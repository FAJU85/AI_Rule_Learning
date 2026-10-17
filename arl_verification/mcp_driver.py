
import asyncio, json, sys, os, time, traceback
def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False)+"\n"); sys.stdout.flush()
async def main():
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    p = StdioServerParameters(command=sys.executable,
        args=["-c","from ai_rule_learning_mcp.server import main; main()"], env=dict(os.environ))
    async with stdio_client(p) as (r,w):
        async with ClientSession(r,w) as s:
            init = await s.initialize(); tl = await s.list_tools()
            emit({"event":"ready","server":getattr(init.serverInfo,"name",None),
                  "server_version":getattr(init.serverInfo,"version",None),
                  "protocol":str(init.protocolVersion),
                  "tools":[{"name":t.name,"schema":t.inputSchema} for t in tl.tools]})
            loop = asyncio.get_running_loop()
            while True:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                if not line: break
                req = json.loads(line)
                if req.get("quit"): break
                t0 = time.perf_counter()
                try:
                    res = await s.call_tool(req["tool"], req.get("args",{}))
                    text = "\n".join(getattr(c,"text","") for c in res.content)
                    emit({"event":"result","id":req["id"],"isError":bool(res.isError),
                          "text":text,"ms":(time.perf_counter()-t0)*1000})
                except Exception as e:
                    emit({"event":"result","id":req["id"],"isError":True,
                          "text":f"EXC {type(e).__name__}: {e}","ms":(time.perf_counter()-t0)*1000})
try: asyncio.run(main())
except BaseException as e:
    emit({"event":"fatal","error":f"{type(e).__name__}: {e}","tb":traceback.format_exc()[-1500:]})
