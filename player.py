import sysv_ipc
import sys
import os
from multiprocessing import shared_memory
import threading

myCards = []
pid = -1
messageQueue = ""
sharedMemory = ""

def readMq(mq):
    while True:
        try:
            message, t = mq.receive(True, 1)
            value = message.decode()
            if value == "terminate":
                print("Server decided to close the connection.")
                sharedMemory.close()
                os._exit(0)
            print("Game is talking to me")
        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            sharedMemory.close()
            os._exit(1)

def initPlayer():
    global pid
    global messageQueue
    global sharedMemory
    try:
        pid = int(sys.argv[1])
    except ValueError:
        print("Incorrect pid passed.")
        os.Exit(2)
   
    mq_key = 128+pid
    try:
        messageQueue = sysv_ipc.MessageQueue(mq_key)
    except sysv_ipc.ExistentialError:
        print("Game process do not accept your Player ID.")
        os._exit(1)
    print("Connected to MessageQueue")
    msg = "hello "+str(pid)
    messageQueue.send(str(msg).encode(), True, 2)
    print("Message '"+msg+"' sended")

    print("Waiting for my cards")
    message, t = messageQueue.receive(True, 1)
    value = message.decode()
    print("Received "+value)
    value = value.split(" ")
    cards_string = value[1].split(",")
    for card in cards_string:
        myCards.append(card)
    shm_key = value[0]
    sharedMemory = shared_memory.SharedMemory(shm_key)
    print("Connected to shared mem")
    mqThread = threading.Thread(target=readMq, args = (messageQueue,))
    mqThread.start()
    print("Thread started")

print("Starting player process")
initPlayer()