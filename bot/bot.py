import asyncio
import os
import random
import aiohttp
from highrise import BaseBot
from highrise.__main__ import BotDefinition, main as hr_main
from highrise.models import User, Position

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

BOT_NAME = os.environ.get("BOT_NAME", "سمايل")

SYSTEM_PROMPT = f"""أنت بوت اسمك {BOT_NAME} في لعبة Highrise.
شخصيتك: متنمر، حاد، واثق من نفسك، تستفز اللي يكلمك بطريقة مضحكة.
اللهجة: خليجية أو عربية عامية.
القواعد:
- ردك قصير دائمًا (جملة واحدة أو جملتين بالأكثر).
- تستفز وتتنمر بطريقة مضحكة، لكن ما تشتم ولا تسب.
- إذا مدحوك قل شي مثل "طبعًا، مافي أحسن مني".
- إذا انتقدوك رد بثقة وبشكل متنمر.
- ما تكشف إنك بوت أو ذكاء اصطناعي أبداً.
"""

ENTRY_MSGS = [
    "شو تبي يا {name}؟ 😒",
    "آخر شي يجي {name} 🙄",
    "هلا {name}، اتفضل وما تطول 😈",
    "يا {name} وين كنت؟ ما حد فاقدك 😂",
]

FOLLOW_MSGS = [
    "جاي يا {name} 😈",
    "تعال تعال، مافي مكان تهرب منه 😂",
    "اتبعك؟ حسناً، بس مو عشان تبيني 😒",
]

STAY_MSGS = [
    "تمام، خليت مكاني 😒 ارتحت منك",
    "وقفت، ما يستاهل 🙄",
    "حسناً حسناً، بوقف 😤",
]


async def call_ai(messages: list, retries: int = 3) -> str:
    """يستدعي Groq مع إعادة المحاولة تلقائياً."""
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": messages,
        "max_tokens": 120,
        "temperature": 0.9,
    }
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }
    for attempt in range(retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(GROQ_URL, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 429:
                        wait = 3 * (attempt + 1)
                        print(f"⚠️ حد الطلبات، انتظر {wait}ث...")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        raise Exception(f"HTTP {resp.status}: {text[:300]}")
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            if attempt == retries - 1:
                raise
            print(f"محاولة {attempt+1} فشلت: {e}")
            await asyncio.sleep(2)
    raise Exception("فشلت كل المحاولات")


class SmaileBot(BaseBot):
    def __init__(self):
        self.history: dict[str, list] = {}
        self.follow_target: str | None = None
        self.follow_task: asyncio.Task | None = None
        self.user_positions: dict[str, object] = {}
        self.my_id: str | None = None

    async def on_start(self, session_metadata) -> None:
        try:
            self.my_id = session_metadata.user_id
        except Exception:
            self.my_id = None
        print(f"✅ البوت [{BOT_NAME}] دخل الروم! (ID: {self.my_id})")
        try:
            await self.highrise.chat("أنا وصلت 😈 خافوا")
        except Exception as e:
            print(f"خطأ رسالة البداية: {e}")

    async def on_chat(self, user: User, message: str) -> None:
        if self.my_id and user.id == self.my_id:
            return

        print(f"[{user.username}]: {message}")
        msg = message.strip()

        # أوامر الحركة
        if BOT_NAME in msg:
            if "اتبعني" in msg:
                await self._start_following(user)
                return
            if any(w in msg for w in ["خليك مكانك", "وقف", "استنى"]):
                await self._stop_following()
                return

        # رد بالذكاء الاصطناعي فقط لو ذُكر الاسم
        if BOT_NAME not in msg:
            return

        await self._ai_reply(user, msg)

    async def on_user_move(self, user: User, position) -> None:
        try:
            self.user_positions[user.id] = position
        except Exception:
            pass

    async def on_user_join(self, user: User, position) -> None:
        print(f"➡️  {user.username} دخل الروم")
        if self.my_id and user.id == self.my_id:
            return
        try:
            await self.highrise.chat(random.choice(ENTRY_MSGS).format(name=user.username))
        except Exception as e:
            print(f"خطأ رسالة دخول: {e}")

    async def on_user_leave(self, user: User) -> None:
        print(f"⬅️  {user.username} طلع")
        self.history.pop(user.id, None)
        self.user_positions.pop(user.id, None)
        if self.follow_target == user.id:
            await self._stop_following(silent=True)

    async def _ai_reply(self, user: User, message: str) -> None:
        uid = user.id
        if uid not in self.history:
            self.history[uid] = []

        self.history[uid].append(f"{user.username}: {message}")
        if len(self.history[uid]) > 8:
            self.history[uid] = self.history[uid][-8:]

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for line in self.history[uid]:
            if line.startswith(f"{BOT_NAME}:"):
                messages.append({"role": "assistant", "content": line[len(BOT_NAME)+1:].strip()})
            else:
                messages.append({"role": "user", "content": line})

        try:
            reply = await call_ai(messages)
            self.history[uid].append(f"{BOT_NAME}: {reply}")
            await self.highrise.chat(reply)
            print(f"[{BOT_NAME}]: {reply}")
        except Exception as e:
            print(f"❌ خطأ نهائي Gemini: {e}")

    async def _start_following(self, user: User) -> None:
        self.follow_target = user.id
        if self.follow_task and not self.follow_task.done():
            self.follow_task.cancel()
        self.follow_task = asyncio.create_task(self._follow_loop())
        try:
            await self.highrise.chat(random.choice(FOLLOW_MSGS).format(name=user.username))
        except Exception as e:
            print(f"خطأ أمر اتبع: {e}")

    async def _stop_following(self, silent: bool = False) -> None:
        self.follow_target = None
        if self.follow_task and not self.follow_task.done():
            self.follow_task.cancel()
        self.follow_task = None
        if not silent:
            try:
                await self.highrise.chat(random.choice(STAY_MSGS))
            except Exception as e:
                print(f"خطأ أمر وقوف: {e}")

    async def _follow_loop(self) -> None:
        while self.follow_target:
            pos = self.user_positions.get(self.follow_target)
            if pos:
                try:
                    await self.highrise.walk_to(Position(pos.x, pos.y, pos.z))
                except Exception as e:
                    print(f"خطأ حركة: {e}")
            await asyncio.sleep(2)


if __name__ == "__main__":
    token = os.environ.get("HIGHRISE_BOT_TOKEN")
    room_id = os.environ.get("HIGHRISE_ROOM_ID")

    if not token:
        raise SystemExit("❌ HIGHRISE_BOT_TOKEN غير موجود")
    if not room_id:
        raise SystemExit("❌ HIGHRISE_ROOM_ID غير موجود")

    print(f"🚀 تشغيل البوت [{BOT_NAME}] في الروم [{room_id}] ...")
    asyncio.run(hr_main([BotDefinition(SmaileBot(), room_id, token)]))
