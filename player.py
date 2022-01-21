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
debug = False
canRefresh = True 
incoming_offer = ""
game_pid = ""

def readMq():
    global gameIsReady
    global serverMessageQueue
    global clientsMsgQueue
    global incoming_offer
    global lock
    global pid
    global myOffer
    global sharedMemory
    global myCards
    
    while True:
        # client <=> server message queue
        try:
            message, t = serverMessageQueue.receive(False, 1)
            value = message.decode()
            value = value.split(" ")
            if value[0] == "terminate":
                print("Server decided to close the connection.")
                terminate(False)
            elif value[0] == "ready":
                gameIsReady = True
            elif value[0] == "gameend":
                gameIsReady = False
                print(f"{value[1]} remporte le round et marque {value[2]} points.")
        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            terminate(False)
        except sysv_ipc.BusyError:
            pass

        # clients <=> clients message queue
        try:
            message, t = clientsMsgQueue.receive(False, pid)
            value = message.decode()
            value = value.split(" ")
            if value[0] == "trade":
                step = value[1]
                from_client = value[2]
                if step == "0":
                    incoming_offer = value[3]
                    sendToClient(from_client, f"trade 1 {pid} {myOffer[0]}")
                elif step == "1":
                    incoming_offer = value[3]
                    with lock:
                        sharedMemory.buf[pid-1] = 0
                    counter = 0
                    for i in range (0,5):
                        if myCards[i] == myOffer[0]:
                            myCards[i] = incoming_offer
                            counter += 1
                        if counter == myOffer[1]: break
                    myOffer = ()
                    incoming_offer = ""
                    
                    new_cards = "Mes cartes : "
                    for card in myCards:
                        new_cards += card+","
                    new_cards = new_cards[:len(new_cards)-1]
                    print(new_cards)
                    sendToClient(from_client, f"trade 2 {pid}")
                elif step == "2":
                    with lock:
                        sharedMemory.buf[pid-1] = 0
                    counter = 0
                    for i in range (0,5):
                        if myCards[i] == myOffer[0]:
                            myCards[i] = incoming_offer
                            counter += 1
                        if counter == myOffer[1]: break
                    myOffer = ()
                    incoming_offer = ""

                    new_cards = "Mes cartes : "
                    for card in myCards:
                        new_cards += card+","
                    new_cards = new_cards[:len(new_cards)-1]
                    print(new_cards)

        except sysv_ipc.ExistentialError:
            print("MessageQueue has been destroyed, connection has been closed.")
            terminate(False)
        except sysv_ipc.BusyError:
            pass

def sendToClient(target_pid, msg):
    global clientsMsgQueue
    global debug
    target_pid = int(target_pid)
    if debug:
        print(f"Sending to client {target_pid} : {msg}")
    msg = msg.encode()
    clientsMsgQueue.send(msg, True, target_pid)
    if debug:
        print(f"Message sended")

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
    if signal == 2: #SIGINT
        terminate()
    elif signal == 3: #SIGQUIT
        print("Un joueur a sonné la fin du round.")

def initPlayer():
    global pid
    global serverMessageQueue
    global sharedMemory
    global threads
    global clientsMsgQueue
    global debug
    global game_pid
    if len(sys.argv) != 2: #check que le nombre d'arguments est correct
        print("Syntax: python3 player.py <pid>")
        os._exit(1)
    try: #si le pid renseigné est correct
        pid = int(sys.argv[1]) # initialisation de la valeur du pid
    except ValueError: #si la saisie du pid n'est pas valide
        print("Incorrect pid passed.") 
        os._exit(1)
   
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
    msg = f"hello {pid} {os.getpid()}" #msg hello
    sendToServer(msg) #envoie le hello au serveur
    if debug:
        print("Message '"+msg+"' sended") #debug, vérification dans le terminal que le msg a bien été envoyé
        print("Waiting for my cards")
    message, t = serverMessageQueue.receive(True, 1)
    value = message.decode() #décode le msg en bit reçu de la mq et le stocke dans value
    if debug: print("Received "+value) #debug
    value = value.split(" ") #split le string value en tableau, la séparation d'une case se fait lorsqu'un espace est rencontré
    cards_string = value[2].split(",")
    for card in cards_string:
        myCards.append(card) #on ajoute la carte en fin de liste
    print("Mes cartes : "+value[2]) #affichage du jeu de cartes
    game_pid = value[0]
    shm_key = value[1]
    sharedMemory = shared_memory.SharedMemory(shm_key)
    if debug: print("Connected to shared mem")
    mqThread = StoppableThread(target=readMq)
    mqThread.start()
    threads.append(mqThread)
    if debug: print("Thread started")
    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGQUIT, signalHandler)
    

def refresh(): #methode permettant de rafraichir l'affichage des offres courantes (cet affichage se fait toutes les 5 secondes)
    global lock
    global myCards
    global canRefresh
    while True:
        time.sleep(5) #permet de faire une pause de 5 secondes dans l'exécution
        if canRefresh:
            with lock:
                if sharedMemory.buf[0] or sharedMemory.buf[1] or sharedMemory.buf[2] or sharedMemory.buf[3] or sharedMemory.buf[4]: #check si un des joueurs a formulé une offre
                    print("\n\n\n\nOffres courantes :")
                    for i in range(0,5): #parcours de la shm
                        if not sharedMemory.buf[i]: #check si la shm n'est pas vide
                            continue
                        print(f"- Player {i+1} : {sharedMemory.buf[i]} cards") #affichage de l'offre du joueur d'indice i
                    string = "\n\n\nMon jeu : "
                    for card in myCards: #parcours du tableau myCards
                        string += card+","
                    string = string[:len(string)-1] #on retire la dernière virgule
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
        choix = choix.split(" ") #split le string choix en un tableau de string, la séparation des cases se fait quand un espace survient dans le string choix
        if len(choix) == 1 and choix[0] == "cancel":
            return False
        if len(choix) != 2: #check que le user a bien spécifié le bon nombre d'arguments
            print("Vous n'avez pas spécifié le bon nombre d'argument : <carte> <nombre>")
        else:
            try:
                carte = choix[0] # la case d'indice 0 du tableau correspond au type de carte
                nombre = int(choix[1]) #conversion de la case d'indice 1 du tableau en int, le nombre de cartes échangées est bien sûr un int
                if myCards.count(carte) < nombre: #check que le nb de cartes que l'on veut l'on a n'est pas plus petit que le nombre de cartes que l'on veut échanger(pour le type donné)
                    print("Vous ne pouvez pas proposer des cartes que vous n'avez pas.")
                elif nombre > 3: #check que le player ne souhaite pas échanger plus de 3 cartes
                    print("Vous ne pouvez pas proposer plus de 3 cartes.")
                else:
                    break
            except ValueError: #check que la saisie du nombre de cartes est valide
                print("Vous n'avez pas entré le bon nombre")
    myOffer = (carte, nombre)
    with lock:
        sharedMemory.buf[pid-1] = myOffer[1]
    return True

def accepterOffre():
    global myOffer
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
            if (target_pid == "cancel"): #permet d'annuler l'opération accepter offre si le joueur s'est trompé de commande
                print("Opération annulée.")
                return
            target_pid = int(target_pid) #conversion du string en int
            if (target_pid != pid): #vérifie que le pid dont on veut accepter l'offre est bien différent du notre
                break
            else:
                print("Vous ne pouvez pas accepter votre propre offre.")
        except ValueError:
            print("Incorrect ID") # permet de ne pas planter le programme en cas de saisie invalide
    with lock:
        if sharedMemory.buf[target_pid-1] == 0: #accède à la valeur stockée dans la share memory et check si une offre a été faite par le joueur ciblé
            print("Le joueur ciblé n'a pas fait d'offre, opération impossible.")
            return
    if not myOffer: #teste si le tuple myOffer est vide ou non
        print (" Veuillez formuler une offre : ")
        faireOffre()

    target_nombre = 0
    with lock:
        target_nombre = sharedMemory.buf[target_pid-1]
    while myOffer[1] != target_nombre: #verifie que le nombre de cartes offert correspond au nb de cartes de l'offre acceptée
        print("Offres non compatibles, veuillez reformuler une offre : ")
        if faireOffre() == False:
            return
    print("Vous avez accepté l'offre du player "+str(target_pid))
    sendToClient(target_pid, f"trade 0 {pid} {myOffer[0]}") #envoie au client ciblé le nombre de cartes échangées
    

def bell():
    global myCards
    global game_pid
    for i in range (1,5):
        if myCards[i] != myCards[i-1]: #check si le joueur a bien 5 cartes identiques
            print("Vous ne pouvez pas utiliser la cloche car vous n'avez pas 5 cartes identiques !")
            return
    print("Vous avez décidé d'actionner la cloche")
    os.kill(int(game_pid), signal.SIGQUIT) #envoie au serveur un signal de type SIGQUIT
    sendToServer(f"score {myCards[0]}") #envoie au serveur le type de carte du joueur ayant actionné la bell

def trackKeyboard():
    global canRefresh


def game():
    global canRefresh
    while gameIsReady: #verifie que le jeu peut se poursuivre
        print("Que voulez-vous faire ? ")
        action = input() #associe à la variable action le string rentré par le player
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