import signal
from threading import current_thread
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
debug = True
canRefresh = True
incoming_offer = ""

def readMq():
    global gameIsReady
    global serverMessageQueue
    global clientsMsgQueue
    global incoming_offer
    global lock
    global pid
    
    while True:
        try:
            # client <=> server message queue
            message, t = serverMessageQueue.receive(False, 1)
            value = message.decode()
            if value == "terminate":
                print("Server decided to close the connection.")
                terminate(False)
            elif value == "ready":
                gameIsReady = True
            value = value.split(" ")

            # clients <=> clients message queue
            message, t = clientsMsgQueue.receive(False, pid)
            value = message.decode()
            value = value.split(" ")
            if value[0] == "trade":
                step = value[1]
                from_client = value[2]
                print(f"Receiving {value[0]} {step} {from_client}")
                if step == 0:
                    incoming_offer = value[3]
                    sendToClient(from_client, f"trade 1 {pid} {myOffer[0]}")
                elif step == 1:
                    incoming_offer = value[3]
                    sendToClient(from_client, "trade 2")
                elif step == 2:
                    with lock:
                        sharedMemory.buf[pid-1] = 0
                    counter = 0
                    for i in range (0,5):
                        if myCards[i] == myOffer[0]:
                            myCards[i] = incoming_offer[0]
                        counter += 1
                        if counter == myOffer[1]: break
                    myOffer = ()
                    incoming_offer = ""

        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            terminate(False)
        except sysv_ipc.BusyError:
            pass

def sendToClient(target_pid, msg):
    global clientsMsgQueue
    global debug
    if debug:
        print(f"Sending to client {target_pid} : {msg}")
    msg = msg.encode()
    clientsMsgQueue.send(msg, True, target_pid)

def sendToServer(msg):
    global serverMessageQueue
    global debug
    if debug:
        print("Sending to server : " + msg)
    msg = msg.encode()
    serverMessageQueue.send(msg, True, 2)

def terminate(from_client=True):
    global threads
    global gameIsReady
    global clientsMsgQueue
    gameIsReady = False
    if pid == 1:
        print("Closing Clients Msg Queue")
        clientsMsgQueue.remove()
    print("Stopping threads")
    for th in threads: # Terminate all threads
        if th.native_id == current_thread().native_id or not th.is_alive():
            continue
        th.terminate()
    if from_client:
        print("Telling the server i want to leave...")
        sendToServer("goodbye") # Tells the server i want to leave
    time.sleep(1)
    sharedMemory.close()
    print("SharedMemory closed")
    print("Closing...")
    os._exit(0)

def signalHandler(signal, frame):
    if signal == signal.SIGINT:
        terminate()
    elif signal == signal.SIGQUIT:
       pass

def initPlayer():
    global pid
    global serverMessageQueue
    global sharedMemory
    global threads
    global clientsMsgQueue
    global debug
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
    if debug:
        print("Connected to MessageQueue")
    msg = "hello "+str(pid)
    sendToServer(msg)
    if debug:
        print("Message '"+msg+"' sended")
        print("Waiting for my cards")
    message, t = serverMessageQueue.receive(True, 1)
    value = message.decode()
    if debug: print("Received "+value)
    value = value.split(" ")
    cards_string = value[1].split(",")
    for card in cards_string:
        myCards.append(card)
    print("Mes cartes : "+value[1])
    shm_key = value[0]
    sharedMemory = shared_memory.SharedMemory(shm_key)
    if debug: print("Connected to shared mem")
    mqThread = StoppableThread(target=readMq)
    mqThread.start()
    threads.append(mqThread)
    if debug: print("Thread started")
    signal.signal(signal.SIGINT, signalHandler)
    

def refresh():
    global lock
    global myCards
    global canRefresh
    while True:
        time.sleep(5)
        if canRefresh:
            with lock:
                if sharedMemory.buf[0] or sharedMemory.buf[1] or sharedMemory.buf[2] or sharedMemory.buf[3] or sharedMemory.buf[4]:
                    print("\n\n\n\nOffres courantes :")
                    for i in range(0,5):
                        if not sharedMemory.buf[i]:
                            continue
                        print(f"- Player {i+1} : {sharedMemory.buf[i]} cards")
                    string = "\n\n\nMon jeu : "
                    for card in myCards:
                        string += card+","
                    string = string[:len(string)-1]
                    print(string)

def faireOffre():
    global myOffer
    global lock
    global canRefresh
    print("Ecrivez <carte> <nombre> ou tapez cancel pour annuler")
    carte = ""
    nombre = 0
    while True:
        canRefresh = False
        choix = input()
        canRefresh = True
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
    global lock
    global pid
    global canRefresh
    target_pid = ""
    while True:
        canRefresh = False
        target_pid = input("pid = ")
        canRefresh = True
        try:
            if (target_pid == "cancel"):
                print("Opération annulée.")
                return
            target_pid = int(target_pid)
            if (target_pid != pid):
                break
            else:
                print("Vous ne pouvez pas accepter votre propre offre.")
        except ValueError:
            print("Incorrect ID")
    with lock:
        if sharedMemory.buf[target_pid-1] == 0:
            print("Le joueur ciblé n'a pas fait d'offre, opération impossible.")
            return
    if not myOffer: #teste si le tuple myOffer est vide ou non
        print (" Veuillez formuler une offre : ")
        faireOffre()

    target_nombre = 0
    with lock:
        target_nombre = sharedMemory.buf[target_pid-1]
    while myOffer[1] != target_nombre:
        print("Offres non compatibles, veuillez reformuler une offre : ")
        if faireOffre() == False:
            return
    print("Vous avez accepté l'offre du player "+str(target_pid))
    sendToClient(target_pid, f"trade 0 {pid} {myOffer[0]} {myOffer[1]}")
    

def bell():
    global myCards
    for i in range (1,5):
        if myCards[i] != myCards[i-1]:
            print("Vous ne pouvez pas utiliser la cloche car vous n'avez pas 5 cartes identiques !")
            return
    print("Vous avez décidé d'actionner la cloche")
    signal.signal(signal.SIGQUIT, signalHandler)



def trackKeyboard():
    global canRefresh


def game():
    global canRefresh
    while gameIsReady:
        print("Que voulez-vous faire ? ")
        action = input()
        if action == "faireOffre":
            faireOffre()
        elif action == "accepterOffre":
            accepterOffre()
        elif action == "bell":
            bell()


print("Starting player process")
initPlayer()
print("En attente des joueurs...")
while not gameIsReady:
    pass
print("Game is ready to start!")
nonBlockingInput = StoppableThread(target=game)
nonBlockingInput.setName("Game")
nonBlockingInput.start()
threads.append(nonBlockingInput)
refreshOffres = StoppableThread(target=refresh)
refreshOffres.setName("Refresh")
refreshOffres.start()
threads.append(refreshOffres)
keyboardTracking = StoppableThread(target=trackKeyboard)
keyboardTracking.setName("TrackKeyboard")
keyboardTracking.start()
threads.append(keyboardTracking)