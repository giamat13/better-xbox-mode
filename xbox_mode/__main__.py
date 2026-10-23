import argparse

from .ui import run

parser = argparse.ArgumentParser(prog="xbox_mode", description="Console-style full-screen shell controlled by a gamepad.")
parser.add_argument("--windowed", action="store_true", help="run in a 1280x720 window (no taskbar hiding changes needed)")
parser.add_argument("--smoke", type=int, default=0, metavar="N", help="render N frames and exit")
args = parser.parse_args()
run(smoke_frames=args.smoke, windowed=args.windowed)
