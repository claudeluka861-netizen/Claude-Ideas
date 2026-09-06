import argparse
import logging
import sys
import time
from datetime import datetime

from . import auth, config, doctor, generate, publish, render, server, service, store
from .config import ROOT

log = logging.getLogger("reelforge")


def _setup_logging(to_file=False):
    log.setLevel(logging.INFO)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s  %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(fmt)
    log.addHandler(stream)
    if to_file:
        handler = logging.FileHandler(ROOT / "reelforge.log", encoding="utf-8")
        handler.setFormatter(fmt)
        log.addHandler(handler)


def cmd_generate(cfg, args):
    log.info(f"Generating {args.count} carousel(s) with {cfg['generate']['provider']}")
    generate.generate(cfg, args.count)


def cmd_render(cfg, args):
    pending = [store.get(args.id)] if args.id else store.by_status("draft")
    pending = [p for p in pending if p]
    if not pending:
        return log.info("Nothing to render.")
    log.info(f"Rendering {len(pending)} post(s)")
    render.render_all(cfg, pending)


def cmd_publish(cfg, args):
    if args.id:
        targets = [store.get(args.id)]
    else:
        targets = store.by_status("approved")[: args.count]
    targets = [t for t in targets if t]
    if not targets:
        return log.info("Nothing approved to publish.")
    auth.refresh_if_needed()
    for post in targets:
        log.info(f"Publishing {post['id']}")
        publish.publish_post(post, cfg)


def _make_one(cfg, attempts=3):
    """Generate + render a single carousel, retrying on transient failures."""
    for attempt in range(1, attempts + 1):
        try:
            made = generate.generate(cfg, 1)
            if not made:
                raise RuntimeError("writer returned nothing")
            render.render_all(cfg, made)
            return made[0]
        except Exception as exc:
            wait = min(60 * attempt, 180)
            log.warning(f"  attempt {attempt}/{attempts} failed: {exc}")
            if attempt == attempts:
                raise
            log.info(f"  retrying in {wait}s")
            time.sleep(wait)
    return None


def cmd_run(cfg, args):
    """Generate, render, and publish if publishing is switched on."""
    for i in range(args.count):
        post = _make_one(cfg)
        if not cfg["publish"]["enabled"]:
            continue
        left, _, _ = publish.quota_left()
        if left <= 0:
            log.warning("  Instagram daily quota is used up — stopping here")
            return
        post["status"] = "approved"
        store.save(post)
        publish.publish_post(post, cfg)
    if not cfg["publish"]["enabled"]:
        log.info("publish.enabled is false — slides are in out/, post them by hand.")


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
    installed, detail = service.status()
    print(f"\nBackground service: {detail}")


def cmd_doctor(cfg, args):
    raise SystemExit(1 if doctor.run(cfg) else 0)


def cmd_service(cfg, args):
    if args.action == "install":
        if doctor.run(cfg):
            raise SystemExit(
                "\nNot installing while there are blocking problems above. "
                "Fix them, then run this again."
            )
        print("\n" + service.install())
    elif args.action == "uninstall":
        print(service.uninstall())
    else:
        print(service.status()[1])


def cmd_daemon(cfg, args):
    """The unattended loop. Wakes at each scheduled slot and posts one carousel."""
    _setup_logging(to_file=True)
    times = cfg["schedule"]["times"][: cfg["schedule"]["posts_per_day"]]
    if not times:
        raise SystemExit("No schedule.times set in config.yaml")

    log.info(f"Daemon up. {len(times)} slots/day: {', '.join(times)}")
    fired = set()
    last_token_check = 0.0

    while True:
        try:
            now = datetime.now()
            stamp = now.strftime("%H:%M")
            today = now.strftime("%Y-%m-%d")
            fired = {f for f in fired if f.startswith(today)}  # forget yesterday

            # Keep the Meta token alive; checking once a day is plenty.
            if cfg["publish"]["enabled"] and time.time() - last_token_check > 86400:
                last_token_check = time.time()
                try:
                    auth.refresh_if_needed()
                except Exception as exc:
                    log.warning(f"token check failed: {exc}")

            key = f"{today} {stamp}"
            if stamp in times and key not in fired:
                fired.add(key)
                log.info(f"--- slot {stamp}")
                try:
                    args.count = 1
                    cmd_run(cfg, args)
                except Exception as exc:
                    log.error(f"slot failed, will try again at the next one: {exc}")
        except Exception as exc:  # the loop itself must never die
            log.error(f"daemon loop error: {exc}")
        time.sleep(20)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="reelforge", description="Instagram carousel factory")
    parser.add_argument("--config", help="path to config.yaml")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("doctor", help="check everything is wired up correctly")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("run", help="generate + render (+ publish if enabled)")
    p.add_argument("-n", "--count", type=int, default=1)
    p.set_defaults(func=cmd_run)

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

    p = sub.add_parser("review", help="open the local review site")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("status", help="what is on disk, quota, service state")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("service", help="install/remove the background service")
    p.add_argument("action", choices=["install", "uninstall", "status"])
    p.set_defaults(func=cmd_service)

    p = sub.add_parser("daemon", help="the scheduled loop (usually run by the service)")
    p.set_defaults(func=cmd_daemon)

    args = parser.parse_args(argv)
    if not logging.getLogger("reelforge").handlers:
        _setup_logging()
    cfg = config.load(args.config)
    args.func(cfg, args)
