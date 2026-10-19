"""Build a Pomodoro sequence for the existing authoritative island clock."""


def pomodoro_tasks(title, step, work=25, short_break=5, long_break=15, rounds=4, long_break_every=4):
    work = max(1, min(180, int(work)))
    short_break = max(1, min(30, int(short_break)))
    long_break = max(1, min(60, int(long_break)))
    rounds = max(1, min(12, int(rounds)))
    long_break_every = max(1, min(12, int(long_break_every)))
    tasks = []
    for index in range(1, rounds + 1):
        tasks.append({"title": title, "subtitle": step, "type": "focus",
                      "time": work * 60, "round": index})
        # No final break: finishing the final work period opens the review.
        if index < rounds:
            long = index % long_break_every == 0
            tasks.append({"title": "长休息" if long else "短休息", "subtitle": "放松一下，下一轮会自动开始",
                          "type": "break", "time": (long_break if long else short_break) * 60,
                          "round": index})
    return tasks
