from d4v.tools.capture_round import ROUND_GUIDANCE


def test_capture_round_guidance_mentions_noise_case():
    assert "gold/item noise" in ROUND_GUIDANCE
