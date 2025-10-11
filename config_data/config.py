from dataclasses import dataclass

from environs import Env

'''
    При необходимости конфиг базы данных или других сторонних сервисов
'''


@dataclass
class tg_bot:
    token: str


@dataclass
class DB:
    dns: str


@dataclass
class UserBot:
    api_id: int
    api_hash: str


@dataclass
class NatsConfig:
    servers: list[str]


@dataclass
class Config:
    bot: tg_bot
    db: DB
    nats: NatsConfig
    user_bot: UserBot


def load_config(path: str | None = None) -> Config:
    env: Env = Env()
    env.read_env(path)

    return Config(
        bot=tg_bot(
            token=env('token'),
        ),
        db=DB(
            dns=env('dns')
        ),
        nats=NatsConfig(
            servers=env.list('nats')
        ),
        user_bot=UserBot(
            api_id=int(env('api_id')),
            api_hash=env('api_hash')
        )
    )
