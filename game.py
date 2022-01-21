import sysv_ipc
from multiprocessing import shared_memory
import threading
import sys
import random
import signal
import os
import time

typeTransport = ['pied','velo','voiture','train','avion']
shm_a = shared_memory.SharedMemory(create=True, size=5) #creation de la shared memory
playersConnected = 0 #initialisation du nb de joueurs connectés
playersNumber = 0 #initialisation du nb de joueurs max
cardCounter = {} #initialisation du nb de cartes distribuées
messageQueues = [] #initialisation du tableau de messageQueue
mqThread = ""
processes_ids = []

def chooseRandomCards(): #methode permettant de créer le jeu d'un joueur
    cartes = "" #liste des cartes sous forme de string
    for j in range (0,5):
        k = random.randint(0,playersNumber-1) #choisit un nb random entre 0 et nbPlayers-1
        if typeTransport[k] not in cardCounter:
            cardCounter[typeTransport[k]] = 0 #initialise à zero le nb de cartes de ce type tirées
        while cardCounter[typeTransport[k]] == 5: #boucle permettant de s'assurer qu'on distribue maximum 5 cartes d'un même type
            k = random.randint(0,playersNumber-1)
            if typeTransport[k] not in cardCounter:
                cardCounter[typeTransport[k]] = 0 #initialise à zero le nb de cartes de ce type tirées
        cartes += typeTransport[k] + "," #ajout de la carte à la liste de cartes
        cardCounter[typeTransport[k]] += 1 #incrémente de 1 le nb de cartes du joueur

    cartes = cartes[:len(cartes)-1]

    return cartes
        
def readMq(mq):
    global playersConnected
    global processes_ids
    global typeTransport
    while True:
        try:
            print("Waiting for msg")
            message, t = mq.receive(True, 2) #le true bloque le code à cette ligne tant qu'il n'y a pas de msg sur la mq, le 2 correspond au type de msg que l'on ecoute
            #type 1 : serv vers player ; type 2 : player vers server
            value = message.decode() #decode les bits de la mq
            print("Received "+value) #print le msg décodé
            value = value.split(" ") #crée un tableau à partir du string, la séparation se fait en fonction des espaces
            if value[0] == "hello": #on accède à l'indice 0 de value (que l'on a splité)
                print("Received hello from "+value[1])
                processes_ids[int(value[1])-1] = value[2]
                return_message = f"{os.getpid()} {shm_a.name} {chooseRandomCards()}".encode() #renvoie le process ID du process game, la clé permettant d'accéder à la shared memory et son jeu au player
                mq.send(return_message, True, 1) #envoie le return msg via la mq
                playersConnected += 1 #incrémente de 1 le nb de joueurs connectés

            if value[0] == "goodbye":
                print("One player decide to leave, terminating the game")
                terminate() #appel de la methode terminate, qui supprime toutes les mq, la shared memory... et termine le jeu

            if value[0] == "score":
                points = 5*(typeTransport.index(value[1])+1)
                print(f"{threading.current_thread().name} a fini la partie et a marqué {points} points.")
                broadcast(f"gameend {threading.current_thread().name} {points}")
                time.sleep(2)
                terminate()
        except sysv_ipc.ExistentialError:
            pass

def broadcast(msg):
    print("Broadcasting to all clients : " + msg)
    msg = msg.encode()
    for mq in messageQueues:
        mq.send(msg, True, 1)


def sendToPlayer(pid, msg): #envoie un msg à un player
    print(f"Sending to Player {pid} : {msg}")
    pid -= 1 #la mq est indicée de 0 à 4, mais les pid des joueurs sont indicés de 1 à 5, on enlève 1 à la valeur du pid du joueur pour que les deux soient cohérents
    msg = msg.encode() #encode le msg à envoyer via la mq
    messageQueues[pid].send(msg, True, 1)

def terminate():
    print("Broadcasting termination to all clients")
    broadcast("terminate") # Broadcast to all connected clients we are going to close the connection
    time.sleep(1)
    for mq in messageQueues: #parcours le tableau des mq
        mq.remove() #supprime toutes les mq
    print("Removed message queues")
    shm_a.close() #ferme la shared memeory
    print("SharedMemory closed")
    shm_a.unlink() #detruit la shared memory
    print("Destroyed SharedMemory")
    print("Closing...")
    os._exit(0) 

def signalHandler(signal, frame):
    if signal == 2: #SIGINT
        terminate()
    elif signal == 3: #SIGQUIT
       print("One player pressed the bell, requesting scores.")
       for id in processes_ids:
           os.kill(int(id), 3)

def initGame(): #methode qui initialise le process game
    global playersNumber
    global mqThread
    global processes_ids
    if len(sys.argv) != 2: #check si le nb d'arguments rentrés est correct
        print("Incorrect amount of arguments")
        sys.exit(2)
    number = sys.argv[1]
    try:
        number = int(number) #conversion en int de number
    except ValueError: #si number ne peut pas être converti en int
        print("Incorrect number of players.")
        sys.exit(2)
    playersNumber = number
    for i in range(1,playersNumber+1):
        key = 128+i
        messageQueue = sysv_ipc.MessageQueue(key, sysv_ipc.IPC_CREAT)
        messageQueues.append(messageQueue)
        print(f"Message Queue {key} created")
        mqThread = threading.Thread(target=readMq, args = (messageQueue,))
        mqThread.setName(f"Joueur-{i}")
        mqThread.start()
        print("Thread created")
    processes_ids = [0 for i in range(playersNumber)]
    signal.signal(signal.SIGINT, signalHandler)
    signal.signal(signal.SIGQUIT, signalHandler)

print("Launching game process...")
initGame()
while playersConnected != playersNumber:
    pass

print("All players are ready, starting the game...")
broadcast("ready")
