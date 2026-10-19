import os
import sys
import zipfile
import io

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))  # scripts/coros/
config_path = os.path.dirname(CURRENT_DIR)                # scripts/
sys.path.append(config_path)
sys.path.append(CURRENT_DIR)

from coros_client import CorosClient
from config  import DB_DIR, COROS_FIT_DIR
from coros_db import CorosDB
from garmin.garmin_client import GarminClient


SYNC_CONFIG = {
    'GARMIN_AUTH_DOMAIN': '',
    'GARMIN_EMAIL': '',
    'GARMIN_PASSWORD': '',
    'GARMIN_NEWEST_NUM': 0,
    "COROS_EMAIL": '',
    "COROS_PASSWORD": '',
}

def init(coros_db):
    ## 判断RQ数据库是否存在
    print(os.path.join(DB_DIR, coros_db.coros_db_name))
    if not os.path.exists(os.path.join(DB_DIR, coros_db.coros_db_name)):
        ## 初始化建表
        coros_db.initDB()
    if not os.path.exists(COROS_FIT_DIR):
        os.mkdir(COROS_FIT_DIR)


if __name__ == "__main__":
  # 首先读取 面板变量 或者 github action 运行变量
  for k in SYNC_CONFIG:
      if os.getenv(k):
          v = os.getenv(k)
          SYNC_CONFIG[k] = v

  COROS_EMAIL = SYNC_CONFIG["COROS_EMAIL"]
  COROS_PASSWORD = SYNC_CONFIG["COROS_PASSWORD"]
  corosClient = CorosClient(COROS_EMAIL, COROS_PASSWORD)

  GARMIN_EMAIL = SYNC_CONFIG["GARMIN_EMAIL"]
  GARMIN_PASSWORD = SYNC_CONFIG["GARMIN_PASSWORD"]
  GARMIN_AUTH_DOMAIN = SYNC_CONFIG["GARMIN_AUTH_DOMAIN"]
  GARMIN_NEWEST_NUM = SYNC_CONFIG["GARMIN_NEWEST_NUM"]

  garminClient = GarminClient(GARMIN_EMAIL, GARMIN_PASSWORD, GARMIN_AUTH_DOMAIN, GARMIN_NEWEST_NUM)


  ## db 名称
  db_name = "coros.db"
  ## 建立DB链接
  coros_db = CorosDB(db_name)
  ## 初始化DB位置和下载文件位置
  init(coros_db)

  all_activities = corosClient.getAllActivities()
  if all_activities == None or len(all_activities) == 0:
      exit()
  for activity in all_activities:
      activity_id = activity["labelId"]
      sport_type = activity["sportType"]
      coros_db.saveActivity(activity_id, sport_type)



  un_sync_list = coros_db.getUnSyncActivity()
  if un_sync_list == None or len(un_sync_list) == 0:
      exit()
  for un_sync in un_sync_list:
    try:
      id = un_sync["id"]
      sport_type = un_sync["sportType"]
      file = corosClient.downloadActivitie(id, sport_type)
      raw = file.data
      buf = io.BytesIO(raw)
      if zipfile.is_zipfile(buf):
        buf.seek(0)
        with zipfile.ZipFile(buf) as zf:
          fit_names = [n for n in zf.namelist() if n.endswith('.fit')]
          statuses = []
          for fit_name in fit_names:
            fit_path = os.path.join(COROS_FIT_DIR, f"{id}-{os.path.basename(fit_name)}")
            with open(fit_path, "wb") as fb:
              fb.write(zf.read(fit_name))
            s = garminClient.upload_activity(fit_path)
            print(f"{fit_name} upload status {s}")
            statuses.append(s)
          upload_status = "SUCCESS" if any(s == "SUCCESS" for s in statuses) else statuses[0] if statuses else "UPLOAD_EXCEPTION"
      else:
        file_path = os.path.join(COROS_FIT_DIR, f"{id}.fit")
        with open(file_path, "wb") as fb:
          fb.write(raw)
        upload_status = garminClient.upload_activity(file_path)
        print(f"{id}.fit upload status {upload_status}")
      if upload_status in ("SUCCESS", "DUPLICATE_ACTIVITY"):
        coros_db.updateSyncStatus(id)
      
    except Exception as err:
      print(err)
      coros_db.updateExceptionSyncStatus(id)
  # exit()