import sysv_ipc
import sys
import os
from multiprocessing import shared_memory
import threading

print("Starting player process")
pid = -1
shm_key = ""
try:
    pid = int(sys.argv[1])
except ValueError:
    print("Incorrect pid passed.")
    os.Exit(2)

def readMq(mq):
    global shm_key
    while True:
        message, t = mq.receive()
        value = message.decode().split(" ")

        print("Game is talking to me")

mq_key = 128+pid
mq = sysv_ipc.MessageQueue(mq_key)
print("Connected to MessageQueue")
msg = "hello "+str(pid)
mq.send(str(msg).encode())
print("Message '"+msg+"' sended")

print("Waiting for my cards")
message, t = mq.receive()
value = message.decode()
print("Received "+value)
value = value.split(" ")
shm_key = value[0]
shm_b = shared_memory.SharedMemory(shm_key)
print("Connected to shared mem")


mqThread = threading.Thread(target=readMq, args = (mq,))
mqThread.start()
print("Thread started")