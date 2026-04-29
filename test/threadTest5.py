import concurrent.futures
import time
import random

count = 0

def task_action(task_id):
    global count
    """
    定义任务的操作函数
    :param task_id: 任务的唯一标识符
    """
    print(f"Task {task_id} is running.")
    
    # 模拟任务执行时间，可根据实际情况修改
    time.sleep(random.random() * 10)
    count = count + 1
    print(f"Task {task_id} is completed.")


def main():
    # 创建一个包含 10 个线程的线程池
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # 提交 1000 个任务
        future_to_task = {executor.submit(task_action, i): i for i in range(100)}

        # 等待所有任务完成
        concurrent.futures.wait(future_to_task)

        # # 等待所有任务完成
        # for future in concurrent.futures.as_completed(future_to_task):
        #     task_id = future_to_task[future]
        #     try:
        #         future.result()
        #     except Exception as exc:
        #         print(f'Task {task_id} generated an exception: {exc}')


    print('count=',count)

if __name__ == "__main__":
    main()