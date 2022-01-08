import sysv_ipc
from stoppable_thread import StoppableThread
from multiprocessing import shared_memory
import sys
import random
import signal
import os
import time
from ilock import ILock

typeTransport = ['pied','velo','voiture','train','avion']
shm_a = shared_memory.SharedMemory(create=True, size=5)
playersConnected = 0
playersNumber = 0
cardCounter = {}
messageQueues = []
mqThread = ""
lock = ILock('lock-cambiecolo')

def chooseRandomCards():
    cartes = ""
    for j in range (0,5):
        k = random.randint(0,playersNumber-1)
        if typeTransport[k] not in cardCounter:
            cardCounter[typeTransport[k]] = 0
        while cardCounter[typeTransport[k]] == 5:
            k = random.randint(0,playersNumber-1)
        cartes += typeTransport[k] + ","
        cardCounter[typeTransport[k]] += 1
    cartes.removesuffix(",")
    return cartes
        
def readMq(mq):
    global playersConnected
    while True:
        print("Waiting for msg")
        message, t = mq.receive(True, 2)
        value = message.decode()
        print("Received "+value)
        value = value.split(" ")
        if value[0] == "hello":
            print("Received hello from "+value[1])
            return_message = f"{shm_a.name} {chooseRandomCards()}".encode()
            mq.send(return_message, True, 1)
            playersConnected += 1

        if value[0] == "goodbye":
            print("One player decide to leave, terminating the game")
            terminate()

def broadcast(msg):
    print("Broadcasting to all clients : " + msg)
    msg = msg.encode()
    for mq in messageQueues:
        mq.send(msg, True, 1)

def sendToPlayer(pid, msg):
    print(f"Sending to Player {pid} : {msg}")
    pid -= 1
    msg = msg.encode()
    messageQueues[pid].send(msg, True, 1)

def terminate():
    print("Stopping mqReading thread")
    mqThread.terminate() # Terminate the thread readMq which read the messageQueue as we're going to destroy the mq
    print("Broadcasting termination to all clients")
    broadcast("terminate") # Broadcast to all connected clients we are going to close the connection
    time.sleep(1)
    for mq in messageQueues:
        mq.remove()
    print("Removed message queues")
    shm_a.close()
    print("SharedMemory closed")
    shm_a.unlink()
    print("Destroyed SharedMemory")
    print("Closing...")
    os._exit(0)

def keyboardInterruptHandler(signal, frame):
   terminate()
   
def initGame():
    global playersNumber
    global mqThread
    if len(sys.argv) != 2:
        print("Incorrect amount of arguments")
        sys.exit(2)
    number = sys.argv[1]
    try:
        number = int(number)
    except ValueError:
        print("Incorrect number of players.")
        sys.exit(2)
    playersNumber = number
    for i in range(1,playersNumber+1):
        key = 128+i
        messageQueue = sysv_ipc.MessageQueue(key, sysv_ipc.IPC_CREAT)
        messageQueues.append(messageQueue)
        print(f"Message Queue {key} created")
        mqThread = StoppableThread(target=readMq, args = (messageQueue,))
        mqThread.start()
        print("Thread created")
    signal.signal(signal.SIGINT, keyboardInterruptHandler)

print("Launching game process...")
initGame()
while playersConnected != playersNumber:
    pass

print("All players are ready, starting the game...")
broadcast("ready")
