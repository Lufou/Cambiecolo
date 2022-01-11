import signal
import sysv_ipc
import sys
import os
from multiprocessing import shared_memory
import time
#from ilock import ILock

from stoppable_thread import StoppableThread

myCards = [] #declare le jeu du player
pid = -1
messageQueue = "" #initialisation de la messageQueue
sharedMemory = "" #initialisation de la shared memory
threads = [] #initialise un tableau de threads
gameIsReady = False
#lock = ILock('lock-cambiecolo')
myOffer = ()
canReadOrWriteMemory = True

def readMq(mq):
    global gameIsReady
    global canReadOrWriteMemory
    while True:
        try:
            message, t = mq.receive(True, 1)
            value = message.decode()
            if value == "terminate":
                print("Server decided to close the connection.")
                sharedMemory.close()
                os._exit(0)
            if value == "ready":
                gameIsReady = True
            value = value.split(" ")
            if value[0] == "busyMem" and value[1] != pid:
                canReadOrWriteMemory = False
            if value[0] == "memReady":
                canReadOrWriteMemory = True
            if value[0] == "okToWrite":
                sharedMemory.buf[pid-1] = myOffer[1].to_bytes()
                send("finishedWriting")
        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            sharedMemory.close()
            os._exit(1)

def send(msg):
    print("Sending to server : " + msg)
    msg = msg.encode()
    messageQueue.send(msg, True, 2)

def terminate():
    global threads
    print("Stopping threads")
    for th in threads: # Terminate all threads
        th.terminate()
    print("Telling the server i want to leave...")
    send("goodbye") # Tells the server i want to leave
    time.sleep(1)
    sharedMemory.close()
    print("SharedMemory closed")
    print("Closing...")
    os._exit(0)

def keyboardInterruptHandler(signal, frame):
   terminate()

def initPlayer():
    global pid
    global messageQueue
    global sharedMemory
    global threads
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
    send(msg)
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
    mqThread = StoppableThread(target=readMq, args = (messageQueue,))
    mqThread.start()
    threads.append(mqThread)
    print("Thread started")
    signal.signal(signal.SIGINT, keyboardInterruptHandler)

def refresh():
    #global lock
    global canReadOrWriteMemory
    while True:
        time.sleep(3000)
        if canReadOrWriteMemory:
            print("\n\n\n\nOffres courantes :")
            for i in range(0,5):
                print(f"- Player {i+1} : {sharedMemory.buf[i].decode()} cards")

    #with lock:
        #pass

def faireOffre():
    global myOffer
    print("Ecrivez <carte> <nombre> ou tapez cancel pour annuler")
    carte = ""
    nombre = 0
    while True:
        choix = input()
        choix = choix.split(" ")
        if len(choix) == 1 and choix[0] == "annuler":
            return
        if len(choix) != 2:
            print("Vous n'avez pas spécifier le bon nombre d'argument : <carte> <nombre>")
        else:
            try:
                carte = choix[0]
                nombre = int(choix[1])
                if myCards.count(carte) < nombre:
                    print("Vous ne pouvez pas proposer des cartes que vous n'avez pas.")
                else:
                    break
            except ValueError:
                print("Vous n'avez pas entré le bon nombre")
    while not canReadOrWriteMemory:
        pass
    send("shm_write "+str(pid))
    myOffer = (carte, nombre)


def AccepterOffre(pid):
    if not myOffer: #teste si le tuple myOffer est vide ou non
        print (" Veuillez formuler une offre : ")
        faireOffre()
    else:
        print("Vous avez accepté l'offre du player "+pid)
        
    
    

def game():
    global threads
    refreshOffres = StoppableThread(target=refresh)
    refreshOffres.start()
    threads.append(refreshOffres)
    while gameIsReady:
        print("Que voulez-vous faire ?")
        action = input()
        if action == "faireOffre":
            faireOffre()

print("Starting player process")
initPlayer()
print("En attente des joueurs...")
while not gameIsReady:
    pass
print("Game is ready to start!")
nonBlockingInput = StoppableThread(target=game)
nonBlockingInput.start()
threads.append(nonBlockingInput)
#while gameIsReady:
    