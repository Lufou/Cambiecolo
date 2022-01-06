import sysv_ipc
import threading
from multiprocessing import shared_memory
import time

print("Launching game process...")
shm_a = shared_memory.SharedMemory(create=True, size=5)

def readMq(mq):
    while True:
        print("Waiting for msg")
        message, t = mq.receive(True, 1)
        value = message.decode()
        print("Received "+value)
        value = value.split(" ")
        if value[0] == "hello":
            print("Received hello from "+value[1])
            return_message = f"{shm_a.name} velo,velo,voiture".encode()
            mq.send(return_message, True, 0)
for i in range(1,6):
    key = 128+i
    messageQueue = sysv_ipc.MessageQueue(key, sysv_ipc.IPC_CREAT)
    print(f"Message Queue {key} created")
    mqThread = threading.Thread(target=readMq, args = (messageQueue,))
    mqThread.start()
    print("Thread created")