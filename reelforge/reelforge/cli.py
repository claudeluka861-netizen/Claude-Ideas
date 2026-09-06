import argparse
import time
from datetime import datetime

from . import config, generate, publish, render, server, store


def cmd_generate(cfg, args):
    print(f"Generating {args.count} carousel(s) with {cfg['generate']['provider']}...")
    generate.generate(cfg, args.count)


def cmd_render(cfg, args):
    pending = store.by_status("draft") if not args.id else [store.get(args.id)]
    pending = [p for p in pending if p]
    if not pending:
        return print("Nothing to render.")
    print(f"Rendering {len(pending)} post(s)...")
    render.render_all(cfg, pending)


def cmd_publish(cfg, args):
    if args.id:
        targets = [store.get(args.id)]
    else:
        targets = store.by_status("approved")[: args.count]
    targets = [t for t in targets if t]
    if not targets:
        return print("Nothing approved to publish.")
    for post in targets:
        print(f"Publishing {post['id']}...")
        publish.publish_post(post, cfg)


def cmd_run(cfg, args):
    """Generate, render, and (if enabled) publish in one shot."""
    made = generate.generate(cfg, args.count)
    if not made:
        return print("Nothing generated.")
    render.render_all(cfg, made)
    if not cfg["publish"]["enabled"]:
        print("\npublish.enabled is false — slides are in reelforge/out/, post them by hand.")
        return
    for post in made:
        post["status"] = "approved"
        store.save(post)
        publish.publish_post(post, cfg)


def cmd_review(cfg, args):
    server.serve(cfg, port=args.port)


def cmd_status(cfg, args):
    posts = store.all_posts()
    counts = {}
    for post in posts:
        counts[post["status"]] = counts.get(post["status"], 0) + 1
    print(f"{len(posts)} posts on disk")
    for status, n in sorted(counts.items()):
        print(f"  {status:<10} {n}")
    if cfg["publish"]["enabled"]:
        try:
            left, used, total = publish.quota_left()
            print(f"\nInstagram: {used}/{total} posts used in the last 24h, {left} left.")
        except Exception as exc:
            print(f"\nCould not read Instagram quota: {exc}")


def cmd_daemon(cfg, args):
    """Sleep until each scheduled time, then make and post one carousel."""
    times = cfg["schedule"]["times"][: cfg["schedule"]["posts_per_day"]]
    if not times:
        raise SystemExit("No schedule.times set in config.yaml")
    print(f"Daemon running. Slots today: {', '.join(times)}")
    print("Leave this open. Ctrl+C to stop.")
    fired = set()
    while True:
        now = datetime.now()
        stamp = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")
        fired = {f for f in fired if f.startswith(today)}  # forget yesterday's slots
        key = f"{today} {stamp}"
        if stamp in times and key not in fired:
            fired.add(key)
            print(f"\n[{key}] slot reached")
            try:
                args.count = 1
                cmd_run(cfg, args)
            except Exception as exc:
                print(f"  slot failed: {exc}")
        time.sleep(20)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reelforge", description="Instagram carousel factory")
    parser.add_argument("--config", help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("generate", help="write new carousels")
    p.add_argument("-n", "--count", type=int, default=1)
    p.set_defaults(func=cmd_generate)

    p = sub.add_parser("render", help="turn drafts into PNG slides")
    p.add_argument("--id")
    p.set_defaults(func=cmd_render)

    p = sub.add_parser("publish", help="push approved carousels to Instagram")
    p.add_argument("--id")
    p.add_argument("-n", "--count", type=int, default=1)
    p.set_defaults(func=cmd_publish)

    p = sub.add_parser("run", help="generate + render (+ publish if enabled)")
    p.add_argument("-n", "--count", type=int, default=1)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("review", help="open the local review site")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("status", help="what is on disk, and Instagram quota")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("daemon", help="run on the schedule in config.yaml")
    p.set_defaults(func=cmd_daemon)

    args = parser.parse_args(argv)
    cfg = config.load(args.config)
    args.func(cfg, args)
