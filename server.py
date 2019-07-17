##############################################################################################################
# Team: Dinh Luong, Yeseul An, Iris Favoreal
# Class: CSS432
# Term project
# Multi-player tic-tac-toe game built on top of TCP socket which allows multiple players to play the game
##############################################################################################################

import socket
import threading
import time
import logging
from sys import argv
from operator import itemgetter


class Server:
    def __init__(self):
        # creating a TCP server socket using IPv4
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)


    def bind(self, port_number):
        # continuously bind port to socket and listen until done succesfully
        while True:
            try:
                self.server_socket.bind(('', int(port_number)))     # bind socket to desired port #
                self.server_socket.listen(1)                        # listen to at least one connection
                print("*************************************************")
                print("Welcome to TIC-TAC-TOE game")
                print("*************************************************")
                print("The server is ready.....")
                return True                                         # if successful, exit loop
            except:
                print("The server cannot be created")


    def close(self):
        self.server_socket.close()      # close server socket


class ServerController(Server):
    def __init__(self):
        Server.__init__(self)


    def unregister(self, player):
        # unregisters a player when the player exits the game completely
        print("Unregistering player: " + player.player_name)
        del self.scoreboard[player.player_name]     # deleting player from scoreboard
        player.send("n", str(0))    # send 0 to client to signal it to call its own unregister function


    def register(self):
        self.room1_pair = []    # array of player partners in room 1
        self.room2_pair = []    # array of player partners in room 2
        self.scoreboard = {}    # contains players along with their score

        # initialize lock for later use
        self.lock_matching = threading.Lock()

        # continuously accept client connections
        # each connection is then serviced in a separate thread
        while True:
            connectionSocket, addr = self.server_socket.accept()    # accept client connection and put into new socket

            p_name = connectionSocket.recv(20).decode()             # receive name of client
            print("Connected with " + p_name)

            self.scoreboard[str(p_name)] = 0                        # add new client into scoreboard

            new_player = GamePlayer(connectionSocket, p_name)       # create new player instance with this client
            new_player.send("s", "Hi " + str(new_player.player_name) + "! You are successfully registered!")
            new_player.send("s", "There are 2 available rooms: [room 1] [room 2]")

            try:
                # service this client in a separate thread
                threading.Thread(target=self.client_thread, args=(new_player,)).start()

            except:
                logging.error("Failed to create a client")


    def client_thread(self, player):
        try:
            # creating message informing about player attendance in room 1
            if len(self.room1_pair)==1:
                msg = "************ Room 1 players: [" + str(self.room1_pair[0].player_name) + "] ************"
            elif len(self.room1_pair)==2:
                msg = "************ Room 1 players: [" + str(self.room1_pair[0].player_name) + "] [" + str(self.room1_pair[1].player_name) + "] ************"
            else:
                msg = "************ Room 1 is empty ************"
            player.send("n", str(len(msg)))     # sending length of message to client so it knows how much to receive from its socket
            player.send("s", msg)               # sending actual message

            # creating message informing about player attendance in room 2 and sending it to client
            if (len(self.room2_pair) == 1):
                msg = "************ Room 2 players: [" + str(self.room2_pair[0].player_name) + "] ************"
            elif (len(self.room2_pair) == 2):
                msg = "************ Room 2 players: [" + str(self.room2_pair[0].player_name) + "] [" + str(self.room2_pair[1].player_name) + "] ************"
            else:
                msg = "************ Room 2 is empty ************"
            player.send("n", str(len(msg)))
            player.send("s", msg)

            roomChosen = player.recv(2, "n")    # receiving client's room choice or if it wishes to register
            print(player.player_name + " selected game room: " + str(roomChosen))

            # room choice 0 means client wishes to unregister
            if roomChosen == 0:
                self.unregister(player)

            # joining room 1
            if roomChosen == 1:
               if len(self.room1_pair) < 2:             # if room is not full,
                    self.room1_pair.append(player)      # we store client into room's array
                    player.send("n", str(1))            # and send the client 1 to signify success
               else:
                   player.send("n", str(2))             # otherwise, we send 2 to signify room is full
                   self.restart(player)                 # then we restart this client_thread function to make them refresh the room state

            # joining room 2
            if roomChosen == 2:
               if len(self.room2_pair) < 2:
                  self.room2_pair.append(player)
                  player.send("n", str(1))
               else:
                  player.send("n", str(2))
                  self.restart(player)

            # once client has chosen room, they will initially be automatically waiting for a match
            while player.is_waiting:
                # try to match client to a player in the same room
                match_result = self.matching_player(player, roomChosen)

                # if no result, sleep for 5 seconds and reloop
                if (match_result is None):
                    time.sleep(5)

                # if there is a match,
                # one client thread will flip both threads to isWaiting = false
                # so the thread that was initially looping will exit this loop and die
                # while the other thread will continue execution here and begin the game between the two clients
                else:
                    new_game = Game()                   # we create a new game instance
                    new_game.p1 = player                # assign the players
                    new_game.p2 = match_result
                    new_game.board = list("         ")  # initialize board
                    new_game.sb = self.scoreboard       # initialize game's scoreboard

                    try:
                        result = new_game.start()       # will start game and return a # to signify result of ended game

                        # if game ends with a 1, that means someone won or game ended in a draw
                        # if game ends with a 2, that means someone exited the game
                        # either way, we want both clients to be removed from the room
                        # and returned to the main menu
                        if(result == 1 or result == 2):

                            # removing clients from room arrays
                            if roomChosen == 1:
                                self.room1_pair.remove(new_game.p1)
                                self.room1_pair.remove(new_game.p2)
                            if roomChosen == 2:
                                self.room2_pair.remove(new_game.p1)
                                self.room2_pair.remove(new_game.p2)

                            # resetting their waiting flags so they can be rematched
                            new_game.p1.is_waiting = new_game.p2.is_waiting = True

                            print("Both players have been removed from room " + str(roomChosen))

                            # sending clients into new threads and servicing them there
                            # then this thread will return and die
                            threading.Thread(target=self.client_thread, args=(new_game.p1,)).start()
                            threading.Thread(target=self.client_thread, args=(new_game.p2,)).start()
                            return

                    except:
                         print("Server cannot create the game between " + str(new_game.p1.player_name) + " and " + str(new_game.p2.player_name))
        except:
            print("Player " + str(player.player_name) + " disconnected")


    def restart(self,player):
        self.client_thread(player)


    def matching_player(self, player1, roomNumber):

        # client chose room 1
        if roomNumber == 1:

            # accessing thread will acquire lock so that no other thread accesses this concurrently
            self.lock_matching.acquire()

            try:
                # checks each player in room's array
                for player2 in self.room1_pair:
                    # Matches the current player with another player in the room1
                    if (player2.is_waiting and player2 is not player1):
                        player1.match = player2
                        player2.match = player1
                        player1.role = "X"
                        player2.role = "O"
                        player1.is_waiting = player2.is_waiting = False

                        msg = "We found you an opponent: " + str(player2.player_name) + " | Your role in the game is: " + player1.role
                        player1.send("n",str(len(msg)))
                        player1.send("s", msg)

                        msg = "We found you an opponent: " + str(player1.player_name) + " | Your role in the game is: " + player2.role
                        player2.send("n",str(len(msg)))
                        player2.send("s", msg)

                        return player2
            finally:
                self.lock_matching.release()        # releasing lock

        # client chooses room #2 instead
        elif roomNumber == 2:
            self.lock_matching.acquire()
            try:
                for player2 in self.room2_pair:
                    # Matches the current player with another player in the room2
                    if (player2.is_waiting and player2 is not player1):
                        player1.match = player2
                        player2.match = player1
                        player1.role = "X"
                        player2.role = "O"
                        player1.is_waiting = player2.is_waiting = False

                        msg = "We found you an opponent: " + str(player2.player_name) + " | Your role in the game is: " + player1.role
                        player1.send("n",str(len(msg)))
                        player1.send("s", msg)

                        msg = "We found you an opponent: " + str(player1.player_name) + " | Your role in the game is: " + player2.role
                        player2.send("n",str(len(msg)))
                        player2.send("s", msg)

                        return player2
            finally:
                self.lock_matching.release()
        return None


class GamePlayer(ServerController):
    #Count the players
    count = 0

    def __init__(self, connection, p_name):
        # initializing player with its variables
        GamePlayer.count = GamePlayer.count+1
        self.id = GamePlayer.count
        self.connection = connection
        self.player_name = p_name
        self.is_waiting = True


    def send(self, command_type, msg):
        try:
            # sending a message and the type of message to client
            # the commands are q for error msg; n for number (probably msg length); s for sentences
            self.connection.send((command_type + msg).encode())
        except:
            self.connection_lost()


    def recv(self, size, type):
        try:
            # receiving message up to a limited size
            msg = self.connection.recv(size).decode()

            # if message type is q or not the type we are expecting
            if (msg[0] == "q" or msg[0] != type):
                self.connection_lost()

            # if message type is n, it is a number so convert message into int type
            elif(msg[0] == "n"):
                return int(msg[1:])

            else:
                return msg[1:]
        except:
            self.connection_lost()
            return None


    def connection_lost(self):
        logging.warning("Player name: " + self.player_name + "| Player ID:" + str(self.id) + " --> connection lost.")
        try:
            # send error message to other player
            self.match.send("q", "The other player lost connection.\nGame over.")
        except:
            pass;
        raise Exception


class Game:
    def start(self):
            while True:
                # Player 1 move
                p1_move = self.move(self.p1, self.p2)
                if(p1_move == 1 or p1_move == 2):       # if move results in a win/loss/exit
                    return p1_move                      # we return that result for further processing

                # Player 2 move
                p2_move = self.move(self.p2, self.p1)
                if(p2_move == 1 or p2_move == 2):
                    return p2_move


    def move(self, curPlayer, waitPlayer):
        curPlayer.send("d", ("".join(self.board)))          # server tells current player to display the board
        curPlayer.send("m", "y")                            # current player is asked for their move input
        waitPlayer.send("d", ("".join(self.board)))         # server tells waiting player to display the board
        waitPlayer.send("m", "n")                           # waiting player is told to wait

        move = int(curPlayer.recv(2, "n"))                  # we receive current's player move input

        if (move == 0):                                     # if move is 0, current player wants to exit
            print(curPlayer.player_name + " has exited the game.")
            waitPlayer.send("n", str(move))                 # we let other player know the 0 move to signify the opponent has exited
            return 2

        waitPlayer.send("n", str(move))                     # if move is not 0, we let other player know the chosen tile

        if (self.board[move - 1] == " "):                   # if tile is valid and not chosen before,
            self.board[move - 1] = curPlayer.role           # we mark the tile as the current player's role

        result, winning_path = self.check_winner(curPlayer) # check if the move is a winning move

        if (result >= 0):
            curPlayer.send("d", ("".join(self.board)))
            waitPlayer.send("d", ("".join(self.board)))

            if (result == 0):                               # if move results in 0, the game is in a draw
                curPlayer.send("m", "d")                    # signify clients for result
                waitPlayer.send("m", "d")
                print("This game ends with a draw.")
                return 1                                    # return 1 to signify draw for further processing

            if (result == 1):                               # result = 1 = someone won and someone lost
                curPlayer.send("m", "w")                    # signify current player that they won
                waitPlayer.send("m", "L")                   # signify waiting player they lost
                curPlayer.send("p", winning_path)           # send to clients the winning path
                waitPlayer.send("p", winning_path)
                print("Player " + str(self.p1.player_name) + " wins the game!")

                winner = str(self.p1.player_name)

                if winner in self.sb:       # store winner in scoreboard
                    self.sb[winner] += 1

                self.printScore(curPlayer, waitPlayer)
                return 1

            return 0

    def printScore(self, curPlayer, waitPlayer):
        print("--------------------------------------------------")
        print("--------------- CURRENT SCOREBOARD ---------------")

        kvp_pairs = len(self.sb.items())

        # let players know the number of key value pairs in scoreboard dict
        curPlayer.send("n", str(kvp_pairs))
        waitPlayer.send("n", str(kvp_pairs))


        for key, value in sorted(self.sb.items(), key=itemgetter(1), reverse=True):
            s = str(key) + ": " + str(self.sb.get(key))

            digit = self.checkSize(s)
            print(s)

            curPlayer.send("n", str(digit)) # send a signal of number of characters in a pair
            waitPlayer.send("n", str(digit))

            lengthS = len(s)
            curPlayer.send("n", str(lengthS))   # send actual length of number of characters in one pair
            waitPlayer.send("n", str(lengthS))

            curPlayer.send("s", str(s))  # send 1 pair in a string
            waitPlayer.send("s", str(s))
        print("--------------------------------------------------")

    def check_winner(self, player):
        s = self.board

        # checking if all possible winning paths have been filled by a specific role
        # and returning 1 if it has

        if (len(set([s[0], s[1], s[2], player.role])) == 1):
            return 1, "012"
        if (len(set([s[3], s[4], s[5], player.role])) == 1):
            return 1, "345"
        if (len(set([s[6], s[7], s[8], player.role])) == 1):
            return 1, "678"

            # Check rows
        if (len(set([s[0], s[3], s[6], player.role])) == 1):
            return 1, "036"
        if (len(set([s[1], s[4], s[7], player.role])) == 1):
            return 1, "147"
        if (len(set([s[2], s[5], s[8], player.role])) == 1):
            return 1, "258"

            # Check diagonal
        if (len(set([s[0], s[4], s[8], player.role])) == 1):
            return 1, "048"
        if (len(set([s[2], s[4], s[6], player.role])) == 1):
            return 1, "246"

        if " " not in s:
            return 0, ""

        return -1, ""

    def checkSize(self, s):
        if len(s) < 10:
            return 0
        if len(s) >= 10 & len(s) < 100:
            return 1

def main():

    serverPort = input("Please enter the server port: ")

    try:
        server = ServerController()
        connected = server.bind(serverPort)

        if (connected):
            server.register()
            #server.close()

    except BaseException as e:
        logging.critical("Server critical failure. \n" + str(e))

if __name__ == "__main__":
	main();