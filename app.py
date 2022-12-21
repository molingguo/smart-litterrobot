import asyncio
from datetime import datetime, timezone

from pylitterbot import Account
from flask import Flask
from flask_cors import CORS
from os import environ
from dotenv import load_dotenv
# from flask_apscheduler import APScheduler

class RobotInfo:
    status = None
    history = None
    insight = None
    last_updated = None
    is_online = None
    litter_level = None
    waste_drawer_level = None
    is_drawer_full_indicator_triggered = None

# set configuration values
# class Config:
#     SCHEDULER_API_ENABLED = True

# EB looks for an 'application' callable by default.
app = Flask(__name__)
load_dotenv()

origins = environ['CORS_ORIGINS'].split(',')
cors = CORS(app, origins=origins)
# application.config.from_object(Config())
app.robot_info = RobotInfo()

# initialize scheduler
# scheduler = APScheduler()
# scheduler.init_app(application)
# scheduler.start()

# @scheduler.task(
#     "interval",
#     id="job_sync",
#     minutes=10,
#     max_instances=1,
# )
# def task1():
#     print("checking robot cycle")
#     asyncio.run(setup_robot(run_cycle_if_necessary = True))

    # oh, do you need something from config?
    # with scheduler.app.app_context():
    #     print(scheduler.app.config)

@app.route("/")
def index():
    asyncio.run(setup_robot())
    robot_info = app.robot_info
    return {
        "last_updated": str(robot_info.last_updated),
        "status": str(robot_info.status),
        "status_text": robot_info.status.text,
        "insight": robot_info.insight,
        "is_online": robot_info.is_online,
        "litter_level": robot_info.litter_level,
        "waste_drawer_level": robot_info.waste_drawer_level,
        "is_drawer_full_indicator_triggered": robot_info.is_drawer_full_indicator_triggered,
        "history": [{
            "timestamp": str(activity.timestamp),
            "action": None if type(activity.action) is str else str(activity.action),
            "text": activity.action if type(activity.action) is str else activity.action.text
        } for activity in robot_info.history]
    }

# @application.route("/job")
# def add_cycle_job():
#     job = scheduler.add_job(
#         func=task1,
#         trigger="interval",
#         minutes=0.2,
#         id="check cycle job",
#         name="check cycle job",
#         replace_existing=True,
#     )
#     return("%s added!" % job.name)

def minutes_diff(time1, time2):
    time_diff = time1 - time2
    duration_in_s = time_diff.total_seconds()
    return divmod(duration_in_s, 60)[0]

async def setup_robot(run_cycle_if_necessary = True):
    last_updated = app.robot_info.last_updated
    if last_updated:
        # print("last_updated: " + str(last_updated))
        diff = minutes_diff(datetime.now(timezone.utc), last_updated)
        if diff < 4:
            return
    # Create an account.
    account = Account()

    try:
        # Connect to the API and load robots.
        username = environ['LR_USERNAME']
        password = environ['LR_PASSWORD']
        await account.connect(username=username, password=password, load_robots=True)

        # Print robots associated with account.
        # print("Robots:")
        for robot in account.robots:
            # print(robot)
            history = await robot.get_activity_history(limit = 500)
            status = robot.status
            if run_cycle_if_necessary and cycle_needed(status, history):
                await robot.start_cleaning()
            # insight = await robot.get_insight()
            # print(insight)
            # insight = None
            app.robot_info.status = status
            app.robot_info.history = history
            app.robot_info.last_updated = datetime.now(timezone.utc)
            app.robot_info.is_online = robot.is_online
            app.robot_info.litter_level = robot.litter_level
            app.robot_info.waste_drawer_level = robot.waste_drawer_level
            app.robot_info.is_drawer_full_indicator_triggered = robot.is_drawer_full_indicator_triggered

    finally:
        # Disconnect from the API.
        await account.disconnect()

def cycle_needed(status, history):
    if str(status) != "LitterBoxStatus.READY":
        print("#### status is not Ready(" + str(status) + "), skip - " + str(datetime.now()))
        return False
    last_activity = history[0]
    if str(last_activity.action) == "LitterBoxStatus.CLEAN_CYCLE_COMPLETE":
        last2_activity = history[1]
        # no cat weight recorded, no need to run again
        # status_to_skip = ["LitterBoxStatus.CLEAN_CYCLE", "LitterBoxStatus.CAT_SENSOR_INTERRUPTED"]
        status_to_skip = ["LitterBoxStatus.CLEAN_CYCLE"]
        if str(last2_activity.action) in status_to_skip:
            print("#### no cat interruppet between cycle, no need to run again - " + str(datetime.now()))
            return False
        minutes = minutes_diff(datetime.now(timezone.utc), last_activity.timestamp)
        if minutes >= 12:
            print("!!!! Run Cycle Needed, start a cycle !!!! - " + str(datetime.now()))
            return True
        else:
            print("#### Run too often, skip for now - " + str(datetime.now()))
            return False
    print("#### Other case, skip for now - " + str(datetime.now()))
    return False

if __name__ == "__main__":
    # asyncio.run(setup_robot())
    # Setting debug to True enables debug output. This line should be
    # removed before deploying a production app.
    # application.debug = True
    app.run()