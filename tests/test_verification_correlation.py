from test_learning_interfaces import Config, initial_team, simulate, world

def test_supervision_reply_is_not_ai_verification():
    cfg=Config();team=initial_team(810002,cfg)
    for event in range(10):
        r=simulate(world(810002,'verification-correlation',event,cfg),team,'G0',cfg,trace=True)
        assert not r['verification'] and not r['verified']
        assert r['verification_token'] is None

def test_verification_is_correlated_and_timely():
    cfg=Config();team=initial_team(810002,cfg)
    completed=0
    for event in range(30):
        r=simulate(world(810002,'verification-correlation',event,cfg),team,'G1',cfg,trace=True)
        if r['verified']:
            completed+=1
            assert r['verification'] and r['verification_reply_time']<=r['publish']
            replies=[m for m in r['trace']['messages'] if m['reply'] and m['request_token']==r['verification_token']]
            assert replies and min(m['processed'] for m in replies)==r['verification_reply_time']
    assert completed
