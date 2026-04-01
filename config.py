import os
TOKEN = os.getenv('DISCORD_TOKEN')

# ------------------ ID каналов ------------------
WELCOME_CHANNEL_ID = 1469706687475875943          # канал для приветствий
LOG_CHANNEL_ID = 1479503694776111206               # канал для логов заходов
REQUEST_CHANNEL_ID = 1469685743579566275           # канал для заявок (входящие)
ACCEPTED_CHANNEL_ID = 1469685873779019800          # канал для принятых заявок
REJECTED_CHANNEL_ID = 1469685977021944001          # канал для отклонённых заявок
BLACKLIST_LOG_CHANNEL_ID = 1479504272432431125     # канал для логов чёрного списка
BLACKLIST_PANEL_CHANNEL_ID = 1479504212105756955   # канал с панелью управления ЧС
APPLICATION_BUTTON_CHANNEL_ID = 1454052533654786118 # канал с кнопкой подачи заявки
PORTFOLIO_CREATION_CHANNEL_ID = 1469700666132795463 # канал с кнопкой создания портфеля
AFK_LOG_CHANNEL_ID = 1479504526007468194           # канал для логов AFK
AFK_PANEL_CHANNEL_ID = 1469704227688419379         # канал с панелью AFK
VACATION_LOG_CHANNEL_ID = 1479504560140587039      # канал для логов отпусков
VACATION_PANEL_CHANNEL_ID = 1469704346978619474    # канал с панелью отпусков
GREEN_REQUESTS_CHANNEL_ID = 1479505188678271107
GREEN_LOG_CHANNEL_ID = 1479505042108059670
LOGGING_CHANNEL_ID = 1453814215960957129  # ID канала для логов
# ------------------ ID ролей ------------------
ROLE_OZON = 1469687547981598946
ROLE_GUEST = 1453818314685022408
ROLE_FAMQ = 1453818745754484850
ROLE_ACADEMY = 1453817578626748628
INVITER_ROLE_ID = 1453817370043748443
LEADER_ROLE_ID = 1453817008826351697
DEPUTY_LEADER_ROLE_ID = 1453817087272157305
VACATION_ROLE_ID = 1469703867418542314
CURATOR_ROLE_ID = 1471533152462704876

# Роли для рангов (портфели)
ACADEMY_ROLE_ID = 1453817578626748628
REED_ROLE_ID = 1453817475828551975
MAIN_ROLE_ID = 1453817433352700067
HIGH_ROLE_ID = 1453817148433502270

# ------------------ ID категорий (портфели) ------------------
ACADEMY_CATEGORY_ID = 1471207559997165795
REED_CATEGORY_ID = 1469721526696939778
MAIN_CATEGORY_ID = 1469713536136773644
HIGH_CATEGORY_ID = 1469719356437954804

# ------------------ ID кастомных эмодзи ------------------
EMOJI_ACCEPT = 1479863953734766743
EMOJI_REJECT = 1479863818573316136
EMOJI_CALL = 1479863915721785456
# ID кастомных эмодзи для портфелей (замените на реальные ID ваших эмодзи)
EMOJI_ACADEMY = "<:Academy:1481338614959968386>"   # эмодзи для Academy
EMOJI_REED = "<:Reed:1481338714985594920>"       # эмодзи для Reed
EMOJI_MAIN = "<:Main:1481338748947140660>"       # эмодзи для Main
EMOJI_HIGH = "<:high:1481339215626240030>"       # эмодзи для High

# ------------------ Прочее ------------------
APPLICATION_BANNER_URL = "https://cdn.discordapp.com/attachments/1476263725735346179/1476995652079845447/image.png?ex=69a326e4&is=69a1d564&hm=2de1512ce783425de92c134e30b5b60f7a4844802264f5b8d571793e81573691&"
VOICE_CHANNEL_ID = 1472308376045228275


ACTIVITY_CHECK_DAYS = 4          # период неактивности в днях
ACTIVITY_CHECK_HOUR = 24         # интервал проверки в часах (например, 24 – раз в сутки)

# Роли, имеющие доступ ко всем портфелям (высокие + лидеры)
PORTFOLIO_ACCESS_ROLES = [
    HIGH_ROLE_ID,
    LEADER_ROLE_ID,
    DEPUTY_LEADER_ROLE_ID
]

# ---------- Каналы для мероприятий ----------
EVENTS_CREATION_CHANNEL_ID = 1469692595260231894   # канал с кнопкой создания
EVENTS_CHANNEL_ID = 1459975955878510726            # канал, куда отправляются мероприятия
EVENTS_LOG_CHANNEL_ID = 1486411401022144825        # канал для логов мероприятий

# ---------- Роли для мероприятий ----------
# Список ролей, которые могут записываться сразу в основной состав (например, "Основной состав")
EVENT_PRIVILEGED_ROLES = [HIGH_ROLE_ID, MAIN_ROLE_ID, DEPUTY_LEADER_ROLE_ID, LEADER_ROLE_ID]  # подставьте ID
# Роли, имеющие административные права (лидер, деп-лидер)
EVENT_ADMIN_ROLES = [LEADER_ROLE_ID, DEPUTY_LEADER_ROLE_ID]

# ---------- Голосовой канал для проверки ----------
EVENT_VOICE_CHANNEL_ID = 1454074855980011762

# ------------------ Настройки логирования бота ------------------
BOT_LOG_CHANNEL_ID = 1483772224065376278   # ID канала для единого лога
LOGGING_ENABLED = True

LOG_LEVELS = {
    'commands': True,
    'events': True,
    'errors': True,
    'ui': True,
    'voice': True,
    'messages': False,
    'debug': True,
    'role_changes': True,
    'http_errors': True,
}
