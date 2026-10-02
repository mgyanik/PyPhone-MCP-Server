from src.policy import evaluate, PolicyDecision

def test_deny_rm_rf():
    assert evaluate('rm -rf /').decision == PolicyDecision.DENY

def test_allow_ls():
    assert evaluate('ls').decision == PolicyDecision.ALLOW

def test_allow_cat():
    assert evaluate('cat /tmp/x').decision == PolicyDecision.ALLOW

def test_unknown_defaults_to_ask():
    assert evaluate('some_unknown_cmd foo').decision == PolicyDecision.ASK
