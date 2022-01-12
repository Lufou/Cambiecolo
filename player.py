import signal
import sysv_ipc
import sys
import os
from multiprocessing import shared_memory
import time
from ilock import ILock

from stoppable_thread import StoppableThread

myCards = [] #declare le jeu du player
pid = -1
serverMessageQueue = "" #initialisation de la messageQueue
sharedMemory = "" #initialisation de la shared memory
threads = [] #initialise un tableau de threads
gameIsReady = False
lock = ILock('lock-cambiecolo')
myOffer = ()
clientsMsgQueue = ""

def readMq():
    global gameIsReady
    global serverMessageQueue
    global clientsMsgQueue
    while True:
        try:
            # client <=> server message queue
            message, t = serverMessageQueue.receive(False, 1)
            value = message.decode()
            if value == "terminate":
                print("Server decided to close the connection.")
                gameIsReady = False
                sharedMemory.close()
                os._exit(0)
            elif value == "ready":
                gameIsReady = True
            value = value.split(" ")

            # clients <=> clients message queue
            message, t = clientsMsgQueue.receive(False, pid)
            value = message.decode()
        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            gameIsReady = False
            sharedMemory.close()
            os._exit(1)
        except sysv_ipc.BusyError:
            pass

def send(msg):
    global serverMessageQueue
    print("Sending to server : " + msg)
    msg = msg.encode()
    serverMessageQueue.send(msg, True, 2)

def terminate():
    global threads
    global gameIsReady
    global clientsMsgQueue
    gameIsReady = False
    if pid == 1:
        print("Closing Clients Msg Queue")
        clientsMsgQueue.remove()
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
    global serverMessageQueue
    global sharedMemory
    global threads
    global clientsMsgQueue
    if len(sys.argv) != 2:
        print("Syntax: python3 player.py <pid>")
        os._exit(1)
    try:
        pid = int(sys.argv[1])
    except ValueError:
        print("Incorrect pid passed.")
        os.Exit(2)
   
    mq_key = 128+pid
    try:
        serverMessageQueue = sysv_ipc.MessageQueue(mq_key)
    except sysv_ipc.ExistentialError:
        print("Game process do not accept your Player ID.")
        os._exit(1)
    if (pid == 1):
        clientsMsgQueue = sysv_ipc.MessageQueue(150, sysv_ipc.IPC_CREAT)
    else:
        clientsMsgQueue = sysv_ipc.MessageQueue(150)
    print("Connected to MessageQueue")
    msg = "hello "+str(pid)
    send(msg)
    print("Message '"+msg+"' sended")

    print("Waiting for my cards")
    message, t = serverMessageQueue.receive(True, 1)
    value = message.decode()
    print("Received "+value)
    value = value.split(" ")
    cards_string = value[1].split(",")
    for card in cards_string:
        myCards.append(card)
    shm_key = value[0]
    sharedMemory = shared_memory.SharedMemory(shm_key)
    print("Connected to shared mem")
    mqThread = StoppableThread(target=readMq)
    mqThread.start()
    threads.append(mqThread)
    print("Thread started")
    signal.signal(signal.SIGINT, keyboardInterruptHandler)

def refresh():
    global lock
    while True:
        time.sleep(3)
        with lock:
            if len(sharedMemory.buf) > 0:
                print("\n\n\n\nOffres courantes :")
                for i in range(0,5):
                    if not sharedMemory.buf[i]:
                        continue
                    print(f"- Player {i+1} : {sharedMemory.buf[i]} cards")

def faireOffre():
    global myOffer
    print("Ecrivez <carte> <nombre> ou tapez cancel pour annuler")
    carte = ""
    nombre = 0
    while True:
        choix = input()
        choix = choix.split(" ")
        if len(choix) == 1 and choix[0] == "annuler":
            return False
        if len(choix) != 2:
            print("Vous n'avez pas spécifié le bon nombre d'argument : <carte> <nombre>")
        else:
            try:
                carte = choix[0]
                nombre = int(choix[1])
                if myCards.count(carte) < nombre:
                    print("Vous ne pouvez pas proposer des cartes que vous n'avez pas.")
                elif nombre > 3:
                    print("Vous ne pouvez pas proposer plus de 3 cartes.")
                else:
                    break
            except ValueError:
                print("Vous n'avez pas entré le bon nombre")
    myOffer = (carte, nombre)
    with lock:
        sharedMemory.buf[pid-1] = myOffer[1]
    return True

def accepterOffre():
    global myOffer #utilise la variable globale myOffer
    global sharedMemory 
    target_pid = input("pid = ")
    if not myOffer: #teste si le tuple myOffer est vide ou non
        print (" Veuillez formuler une offre : ")
        faireOffre()

    '''while myOffer[1] != sharedMemory.buf[target_pid-1]:
        print("Offres non compatibles, veuillez reformuler une offre : ")
        if faireOffre() == False:
            return'''
    print("offres compatibles :) ")
    send("trade "+str(myOffer[1])+" cards "+myOffer[0]+" with player "+str(target_pid))
    print("Vous avez accepté l'offre du player "+str(target_pid))
    
    

def game():
    global threads
    refreshOffres = StoppableThread(target=refresh)
    refreshOffres.start()
    threads.append(refreshOffres)
    while gameIsReady:
        print("Que voulez-vous faire ? ")
        action = input()
        if action == "faireOffre":
            faireOffre()
        elif action == "accepterOffre":
            accepterOffre()

print("Starting player process")
initPlayer()
print("En attente des joueurs...")
while not gameIsReady:
    pass
print("Game is ready to start!")
nonBlockingInput = StoppableThread(target=game)
nonBlockingInput.start()
threads.append(nonBlockingInput)