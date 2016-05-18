import sys
import socket
import string
import psycopg2 as pgsql

if (len(sys.argv) == 2):
  conf_file = sys.argv[1]
else:
  sys.exit();

# lets set some variables
HOSTS = { "freenode": "irc.freenode.net", "OFTC" : "irc.oftc.net" }
PORT = 6667
OWNER = ["list","of","usernames"]
NETWORKS = {}
PASSWORD = ""

# lets define some functions
def sendmsg(sock, msg):
  print "{}".format(msg.strip())
  sock.send(msg)

def logmsg(network, channel, action, user, msg):
  conn = pgsql.connect("""dbname='ircbot' user='postgres' host='localhost' password = 'password'""")
  cur = conn.cursor()
  cur.execute("""insert into irclogs (network, channel, action, nick, message) 
    values (%s, %s, %s, %s, %s)""", (network, channel, action, user, msg))
  conn.commit()

def parsemsg(tokens):
  result = {}
  if (tokens[1] in ["PRIVMSG", "JOIN", "PART"]):
    result['user']    = tokens[0][1:].split("!")[0]
    result['action']  = tokens[1]
    result['channel'] = tokens[2]
    if (result['channel'].startswith(":")):
      result['channel'] = result['channel'][1:]
    if (len(tokens) >= 4):
      result['msg'] = " ".join(tokens[3:])[1:]
    else:
      result['msg'] = ""
    return result
  return False

with open(conf_file, "r") as config:
  network = ""
  for line in config:
    if network:
      if not line.strip():
	network = ""
      else:
        if line.startswith("#"):
	 NETWORKS[network]['channels'].append(line.strip())
        else:
	 NETWORKS[network]['nick'] = line.strip()
    else:
      if line.startswith("["):
        network = line.strip()[1:-1]
	NETWORKS[network] = {}
	NETWORKS[network]['channels'] = []

for network in NETWORKS:
  if network in HOSTS:
    irc_buffer = ""
    host = HOSTS.get(network)
    nick = NETWORKS[network]['nick']

    # connections and stuff
    sock = socket.socket()
    err = sock.connect((host, PORT))
    sendmsg(sock, "USER {} * dormouse :{}\r\n".format(nick, nick))
    sendmsg(sock, "NICK {}\r\n".format(nick))
    motd_sent = False

    # loop and get messages
    while 1:
      irc_buffer=irc_buffer+sock.recv(1024)
      temp=string.split(irc_buffer, "\n")
      irc_buffer=temp.pop()

      for line in temp:
        line=string.rstrip(line)
        print line
        tokens = string.split(line)

	# whenever we receive a ping, send a pong back
	if(tokens[0]=="PING"):
	  sendmsg(sock, "PONG {}\r\n".format(tokens[1]))

	# wait to receive motd
	if (not motd_sent):
	  if ("376" in tokens):
	    motd_sent = True
	    for channel in NETWORKS[network]['channels']:
	      sendmsg(sock, "JOIN {}\r\n".format(channel))
	else:
	  # parse and react to messages
	  tokens = line.split(" ")
	  result = parsemsg(tokens)
	  if (result):
	    if (result['channel'] == nick):
	      if (result['user'] in OWNER):
		if (len(result['msg'].split(" ")) >= 2):
		  [target, msg] = result['msg'].split(" ", 1)
		  sendmsg(sock, "PRIVMSG {} :{}\r\n".format(target, msg))
	      else:
		sendmsg(sock, "PRIVMSG {} :{} said: {}\r\n".format(OWNER, 
		  result['user'], result['msg']))
	    else:
	      if (result['channel'] != nick and result['user'] != nick):
		logmsg(network, result['channel'], result['action'], 
		  result['user'], result['msg'])
