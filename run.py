import argparse
import home_robot_sim as sim
from agent import Agent
from tests import TEST_COMMANDS


def build_robot(args):
    renderer = None
    step_delay = 0.0
    if args.gui:
        renderer = sim.make_pygame_renderer()
        step_delay = 0.02
    elif args.ascii:
        renderer = sim.ascii_renderer
    return sim.Robot(grasp_fail_prob=args.fail, seed=args.seed,
                     renderer=renderer, step_delay=step_delay)


def interactive(args):
    robot = build_robot(args)
    agent = Agent(robot)
    print("Type a request for the robot (or 'quit').")
    while True:
        try:
            cmd = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if cmd.lower() in ("quit", "exit", "q"):
            break
        if cmd:
            agent.handle(cmd)


def run_suite(args):
    for category, command in TEST_COMMANDS:
        print("\n" + "#" * 70)
        print(f"[{category}]  {command}")
        print("#" * 70)
        robot = build_robot(args)
        agent = Agent(robot)
        agent.handle(command)
        if robot._last_speech:
            print(f'   FINAL REPLY: "{robot._last_speech}"')
        else:
            print("   (robot never spoke to the person)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--test", action="store_true")
    p.add_argument("--gui", action="store_true")
    p.add_argument("--ascii", action="store_true")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--fail", type=float, default=0.30)
    args = p.parse_args()

    if args.test:
        run_suite(args)
    else:
        interactive(args)
