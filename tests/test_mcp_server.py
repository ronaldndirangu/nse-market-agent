from nse_agent import engine, mcp_server


def test_analysis_cache_expires(monkeypatch):
    calls, clock = [], [1000.0]
    monkeypatch.setattr(engine, "analyze", lambda **kwargs: calls.append(1) or {"n": len(calls)})
    monkeypatch.setattr(mcp_server.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(mcp_server, "_cache", {})
    assert mcp_server._analysis() == {"n": 1}
    clock[0] += mcp_server.CACHE_SECONDS - 1
    assert mcp_server._analysis() == {"n": 1}
    clock[0] += 2
    assert mcp_server._analysis() == {"n": 2}
