##############################################################################################################
# Team: Dinh Luong, Yeseul An, Iris Favoreal
# Class: CSS432
# Term project
# Multi-player tic-tac-toe game built on top of TCP socket which allows multiple players to play the game
##############################################################################################################

import socket
import threading
import time
from sys import argv
import logging

class Client():
    def __init__(self):
        # creating a TCP client socket using IPv4
        self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM);

    def connect(self, address, port_number):
        # connect to the server with the input IP address and port number
        while True:
            try:
                print("Connecting to the server...")
                self.client_socket.connect((address, int(port_number)))
                return True
            except: # return false if have connection problem
                print("There is an error occured trying to connect to the server")
                return False

    def send_msg(self, c_type, msg):
        # sending a message and the type of message to server
        # the commands are q for error msg; n for number (probably msg length); s for sentences
        try:
            self.client_socket.send((c_type + msg).encode())
        except:
            self.connection_lost()

    def recv_msg(self, size, type):
        # receiving message up to a limited size
        msg = self.client_socket.recv(size).decode()

        # if message type is q, indicates close connection
        if (msg[0] == "q"):
            print(msg[1:])
            raise Exception

        # if message type is n, it is a number so convert message into int type
        elif (msg[0] == "n"):
            return int(msg[1:])

        # if message type is s, it is a sentence from server
        elif (msg[0] == "s"):
            return (msg[1:])

        else:
            return msg[1:]

        return None

    def connection_lost(self):
        try:
            # send error message to server
            self.client_socket.send("q".encode())
        except:
            pass
        raise Exception

    def close(self):
        self.client_socket.close()


class ClientController(Client):
    def __init__(self):
        Client.__init__(self)

    def unregister(self, signal):
        # unregisters a player when the player exits the game completely
        if signal == 0:
            print("Connection closed")
            self.close()  # close the connection

    def start_game(self, playerName):
        # send player name to server for registration
        self.client_socket.send(playerName.encode())

        # receiving greeting message from server if sucessfully connect
        greetingFromServer = self.recv_msg(70, "s")
        print("Greeting from Server: " + greetingFromServer)

        # receiving two rooms message from server for displaying
        roomInfoFromServer = self.recv_msg(54, "s")
        print("Greeting from Server: " + str(roomInfoFromServer))
        self.displayPlayer()

    def displayPlayer(self):
        # receive message from server about the player names in room 1
        # receive the size of message first
        # then receive the message with that specific size
        roomLen1 = int(self.recv_msg(3, "n"))
        roomMsg1 = self.recv_msg(roomLen1 + 1, "s")
        print(roomMsg1)

        # receive message from server about the player names in room 2
        # receive the size of message first
        # then receive the message with that specific size
        roomLen2 = self.recv_msg(3, "n")
        roomMsg2 = self.recv_msg(roomLen2 + 1, "s")
        print(roomMsg2)

        # prompt player to input a room number
        selectRoom = input("Please select a room number: 1~2 or unregister(0): ")
        print("*************************************************")
        print("You select room number: " + str(selectRoom))

        # send the room number to server
        self.send_msg("n", str(selectRoom))

        # receive a message from server about the selected room
        getAccept = self.recv_msg(2, "n")

        # when player choice 0 in input room number means player wishes to unregister
        # server send getAccept message 0 to call protocol to unregister this player
        if getAccept == 0:
            self.unregister(getAccept)
            return

        # server send getAccept message 2 to signify room is full
        # display message to player and call restart to display another room option
        if getAccept == 2:
            print("This room is full. Please select the other room.")
            self.restart()

        # if room is available, display message and ask to wait for another player
        print("Please wait for one more player to join the game")
        print("*************************************************")

        # receive message about matching player
        # receive the size of message first
        # then receive the message with that specific size
        matchLen = self.recv_msg(3, "n")
        getMatch = self.recv_msg(matchLen + 1, "s")
        print(getMatch)

        # call game_start and start the game
        self.game_start()

    # restart will loop back to displayPlayer to let player reselect game room
    def restart(self):
        self.displayPlayer()

    def game_start(self):
        print("**************************** GAME START ****************************")
        while True:
            # message type "d" indicates display board
            # player receives the board content from server
            displayBoard = self.recv_msg(10, "d")

            # message type "m" indicate receive a command from server
            messageFromServer = self.recv_msg(2, "m")

            # player display the game board
            self.update_board(messageFromServer, displayBoard)

            # if server send a command type "y", indicate this player is in playing turn in the game
            # prompt player to select a position to move
            if (messageFromServer == "y"):
                position = int(input("Please enter the position (1~9) or exit(0): "))

                while True:
                    # let player know if they select the position that already been taken
                    # prompt to select another position
                    if (position >= 1 and position <= 9):
                        if (displayBoard[position - 1] != " "):
                            print("That position has already been taken")
                            position = int(input("Please enter the position (1~9) or exit(0): "))
                            pass
                        else:
                            break
                    # if player select 0 indicate they want to exit the game
                    # loop back to displayPlayer protocol to restart the game
                    elif (position == 0):
                        print("You have exited the game.")
                        print("Going back to the main menu...")
                        self.send_msg("n", str(position))
                        self.displayPlayer()
                        return False
                    # handle out of range input and prompt to select again
                    else:
                        print("That position is out of range")
                        position = int(input("Please enter the position (1~9) or exit(0): "))
                        pass

                # player send the input position to server
                self.send_msg("n", str(position))

            # if server send a command type "n", indicate this player is in waiting turn in the game
            # inform player by displaying waiting message and the position that their opponent select
            # inform player if their opponent exit the game, loop back to displayPlayer to restart a new game
            elif (messageFromServer == "n"):
                print("Please wait ............ ")
                opponentMove = self.recv_msg(2, "n")
                if (opponentMove == 0):
                    print("Your opponent has exited the game!")
                    self.displayPlayer()
                    return False
                else:
                    print("Your opponent made a change on number " + str(opponentMove))

            # if server send a command type "d", indicate this game is draw
            elif (messageFromServer == "d"):
                print("This game is draw !!!")
                return True

            # if server send a command type "w", indicate this player is the winner
            elif (messageFromServer == "w"):
                # receive the winning path from server
                getPath = self.recv_msg(4, "s")
                print("You WIN the game !!!")
                print("--------------------------------------------------")
                print("----------This is current scoreboard--------------")
                # display the score board from server
                # receive the number of key value pairs in scoreboard dict
                getTimes = self.recv_msg(2, "b")
                for i in range(0, getTimes):
                    digit = self.recv_msg(2, "n") # receive a signal of number of characters in a pair
                    if digit == 0:
                        length = self.recv_msg(2, "n") # receive actual length of number of characters in one pair

                        score = self.recv_msg(length + 1, "s") # receive a pair in a string
                        print(score)

                    elif digit == 1:
                        length = self.recv_msg(3, "n")  # receive actual length of number of characters in one pair
                        score = self.recv_msg(length + 1, "s") # receive a pair in a string
                        print(score)
                print("--------------------------------------------------")
                self.displayPlayer()  # loop back to displayPlayer to restart the game
                break

            # if server send a command type "L", indicate this player lost the game
            elif (messageFromServer == "L"):
                # receive the winning path from server
                getPath = self.recv_msg(4, "s")
                print("You LOSE the game !!!")
                print("--------------------------------------------------")
                print("----------This is current scoreboard--------------")
                # display the score board from server
                # receive the number of key value pairs in scoreboard dict
                getTimes = self.recv_msg(2, "b")
                for i in range(0, getTimes):
                    digit = self.recv_msg(2, "n") # receive a signal of number of characters in a pair
                    if digit == 0:
                        length = self.recv_msg(2, "n") # receive actual length of number of characters in one pair
                        score = self.recv_msg(length + 1, "s") # receive a pair in a string
                        print(score)
                    elif digit == 1:
                        length = self.recv_msg(3, "n") # receive actual length of number of characters in one pair
                        score = self.recv_msg(length + 1, "s") # receive a pair in a string
                        print(score)
                print("--------------------------------------------------")
                self.displayPlayer() # loop back to displayPlayer to restart the game
                break

    # get the update board content from server and storage in parameter "board"
    # call format_board to display the board content
    def update_board(self, messageFromServer, board):
        # if this player is in playing turn, display the board with the number in the background
        if (messageFromServer == "y"):
            print("")
            print("Current board:\n" + ClientController.format_board(ClientController.display_board(board)))
        # if this player is in waiting turn, display the board without the number in the background
        else:
            # Print out the current board
            print("Current board:\n" + ClientController.format_board(board))

    # display the board with the content in the parameter s get from display_board
    def format_board(s):
        if (len(s) != 9):
            print("Error: there should be 9 symbols.")
            # Throw an error
            raise Exception

        return ("|" + s[0] + "|" + s[1] + "|" + s[2] + "|\n"
                + "|" + s[3] + "|" + s[4] + "|" + s[5] + "|\n"
                + "|" + s[6] + "|" + s[7] + "|" + s[8] + "|\n")

    # parameter "s" content the moving player role in the position they just made changed
    # display_board replace the number to the player role in the board content
    # pass this update board content to format_board
    def display_board(s):
        new_s = list("123456789")
        for i in range(0, 8):
            if (s[i] != " "):
                new_s[i] = s[i]
        return "".join(new_s)

def main():
    print("*************************************************")
    print("Welcome to TIC-TAC-TOE game")
    print("Please register player information")
    print("*************************************************")

    address = input("Please enter the server name: ")
    port_number = input("Please enter the server port(should be same as the server): ")

    if (len(argv) != 2):
        userName = input("Please enter player name(should be less than 20 characters): ")
        print("*************************************************")

    else:
        userName = argv[1]

    client = ClientController()
    connected = client.connect(address, port_number)

    if (connected):
        print("Successfully connected with the server")
        client.start_game(userName)
        client.close()

    else:
        print("Cannot connected with the server")
        client.close()


if __name__ == "__main__":
    main();
