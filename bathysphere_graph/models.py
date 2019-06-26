from secrets import token_urlsafe
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class Entity:

    _verb = False
    _source = None

    def __init__(self, identity: int = None, annotated: bool = False,
                 location: list or tuple or None = None, verb: bool = False):
        """
        Primitive object/entity, may have name and location

        :param identity: Unique identifier, assumed to be integer ID
        :param annotated: Has a name and/or description
        :param location: Coordinates, geographic or cartesian
        """
        self.id = identity
        self._verb = verb
        self._source = "entity.__init__"

        if annotated:
            self.name = None
            self.description = None
        if location:
            self.location = {"type": "Point", "coordinates": location} if type(location) == list else location

        self._notify('created')

    def __del__(self):
        self._notify('removed')

    def _notify(self, message: str) -> None:
        """
        Print notification to commandline if in verbose mode
        """
        if self._verb:
            print(self.name, self.__class__, message)


class Root(Entity):
    def __init__(self, url: str, secretKey: str):
        Entity.__init__(self, identity=0, annotated=True)
        self.name = "root"
        self.url = url
        self._secretKey = secretKey
        self.tokenDuration = 600


class Proxy(Entity):
    def __init__(self, url: str, name: str, description: str, identity: int = None):
        Entity.__init__(self, identity=identity, annotated=True)
        self.name = name
        self.description = description
        self.url = url


class User(Entity):

    _ipAddress = None

    def __init__(self, name: str, credential: str, identity: int = None, description: str = "", ip=None):
        """
        Create a user entity.

        :param name: user name string
        :param identity: optional integer to request (will be automatically generated if already taken)
        """
        Entity.__init__(self, identity=identity, annotated=True)
        self.name = name
        self.alias = name
        self._credential = credential
        self.validated = True
        self._ipAddress = ip
        self.description = description

    def sendCredential(self, text: str, auth: dict):

        server = smtplib.SMTP_SSL(auth["server"], port=auth["port"])
        server.login(auth["account"], auth["key"])

        msg_root = MIMEMultipart()
        msg_root['Subject'] = "Oceanicsdotio Account"
        msg_root['From'] = auth["reply to"]
        msg_root['To'] = self.name

        msg_alternative = MIMEMultipart('alternative')
        msg_root.attach(msg_alternative)
        msg_alternative.attach(
            MIMEText(text)
        )
        server.sendmail(auth["account"], self.name, msg_root.as_string())


class Ingress(Entity):

    _apiKey = None
    _lock = False

    def __init__(self, name, description="", url="", apiKey=None, identity=None):

        Entity.__init__(self, identity=identity, annotated=True)
        self.name = name
        self.description = description
        self.url = url
        self._apiKey = apiKey if apiKey else token_urlsafe(64)


graph_models = {
    Entity,
    Root,
    Proxy,
    User,
    Ingress
}