def dedupe_events(
    events: list[dict[str, int]],
    frame_window: int,
) -> list[dict[str, int]]:
    result: list[dict[str, int]] = []
    last_seen: dict[int, int] = {}

    for event in events:
        frame = event["frame"]
        value = event["value"]
        if value in last_seen and frame - last_seen[value] <= frame_window:
            continue
        last_seen[value] = frame
        result.append(event)

    return result
