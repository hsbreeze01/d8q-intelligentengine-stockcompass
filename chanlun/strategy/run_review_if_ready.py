import sys, os, subprocess, pymysql

REPO = "/home/ecs-assist-user/d8q-intelligentengine-stockcompass"
DB = {"host":"127.0.0.1","port":3306,"user":"root","password":"password","database":"stock_analysis_system","charset":"utf8mb4"}

def main():
    try:
        conn = pymysql.connect(**DB, connect_timeout=10)
    except Exception as e:
        print("DB connect failed: %s" % e); sys.exit(2)
    cur = conn.cursor()
    cur.execute("SELECT MIN(signal_date), MAX(signal_date), COUNT(DISTINCT signal_date) FROM czsc_signal_history")
    row = cur.fetchone()
    cur.close(); conn.close()
    if not row or row[2] is None:
        print("SKIP: no clean signals"); sys.exit(0)
    min_d, max_d, ndays = row
    span = (max_d - min_d).days
    if ndays < 5 or span < 7:
        print("SKIP review: ndays=%s span_days=%s (need ndays>=5 and span>=7)" % (ndays, span)); sys.exit(0)
    print("Running weekly review: ndays=%s span_days=%s" % (ndays, span))
    script = os.path.join(REPO, "chanlun", "strategy", "review_weekly.py")
    py = os.path.join(REPO, "venv", "bin", "python")
    cmd = [py, script]
    # 仅当配置了企微 webhook key 时才推送; 未配置则静默不推(不阻断复盘计算)
    if os.environ.get("D8Q_REVIEW_WECOM_KEY"):
        cmd.append("--push")
    rc = subprocess.run(cmd, cwd=os.path.join(REPO, "chanlun", "strategy")).returncode
    sys.exit(rc)

if __name__ == "__main__":
    main()
