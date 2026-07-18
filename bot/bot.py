import asyncio
import os
import random
import google.generativeai as genai
from highrise import BaseBot
from highrise.__main__ import BotDefinition, main as hr_main
from highrise.models import User, Position

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
gemini_model = genai.GenerativeModel(
    model_name="gemini-pro",
    generation_config={"max_output_tokens": 120, "temperature": 0.9},
)

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

ERROR_MSGS = [
    "ما فهمت وش تبي، كلامك فاضي 😒",
    "إيش هذا الكلام اللي ما يفهم؟ 🙄",
    "حدّث نفسك بس 😂",
]


class SmaileBot(BaseBot):
    def __init__(self):
        self.history: dict[str, list] = {}
        self.follow_target: str | None = None
        self.follow_task: asyncio.Task | None = None
        self.user_positions: dict[str, Position] = {}
        self.my_id: str | None = None

    async def on_start(self, session_metadata) -> None:
        # حفظ ID البوت عشان ما يرد على نفسه
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
        # تجاهل رسائل البوت نفسه
        if self.my_id and user.id == self.my_id:
            return

        print(f"[{user.username}]: {message}")

        msg = message.strip()

        # ── أوامر الحركة (تشتغل لو فيها اسم البوت) ──────────────────
        if BOT_NAME in msg:
            # أمر اتبعني
            if "اتبعني" in msg:
                await self._start_following(user)
                return
            # أمر وقوف
            if any(w in msg for w in ["خليك مكانك", "وقف", "استنى"]):
                await self._stop_following()
                return

        # ── رد بالذكاء الاصطناعي فقط لو ذكر اسم البوت ─────────────
        if BOT_NAME not in msg:
            return

        await self._ai_reply(user, msg)

    async def on_user_move(self, user: User, position) -> None:
        # نحفظ آخر موقع لكل مستخدم عشان نقدر نتبعه
        try:
            self.user_positions[user.id] = position
        except Exception:
            pass

    async def on_user_join(self, user: User, position) -> None:
        print(f"➡️  {user.username} دخل الروم")
        if self.my_username and user.username == self.my_username:
            return
        msg = random.choice(ENTRY_MSGS).format(name=user.username)
        try:
            await self.highrise.chat(msg)
        except Exception as e:
            print(f"خطأ رسالة دخول: {e}")

    async def on_user_leave(self, user: User) -> None:
        print(f"⬅️  {user.username} طلع")
        self.history.pop(user.id, None)
        self.user_positions.pop(user.id, None)
        if self.follow_target == user.id:
            await self._stop_following(silent=True)

    # ── دوال مساعدة ────────────────────────────────────────────────────

    async def _ai_reply(self, user: User, message: str) -> None:
        uid = user.id
        if uid not in self.history:
            self.history[uid] = []

        self.history[uid].append(f"{user.username}: {message}")
        if len(self.history[uid]) > 8:
            self.history[uid] = self.history[uid][-8:]

        try:
            # نبني سياق المحادثة كنص واحد
            context = "\n".join(self.history[uid])
            prompt = f"{SYSTEM_PROMPT}\n\nالمحادثة:\n{context}\n\n{BOT_NAME}:"

            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(
                None,
                lambda: gemini_model.generate_content(prompt)
            )
            reply = resp.text.strip()
            self.history[uid].append(f"{BOT_NAME}: {reply}")
            await self.highrise.chat(reply)
            print(f"[{BOT_NAME}]: {reply}")
        except Exception as e:
            print(f"❌ خطأ Gemini: {e}")
            fallback = random.choice(ERROR_MSGS)
            try:
                await self.highrise.chat(fallback)
            except Exception:
                pass

    async def _start_following(self, user: User) -> None:
        self.follow_target = user.id
        if self.follow_task and not self.follow_task.done():
            self.follow_task.cancel()
        self.follow_task = asyncio.create_task(self._follow_loop())
        msg = random.choice(FOLLOW_MSGS).format(name=user.username)
        try:
            await self.highrise.chat(msg)
        except Exception as e:
            print(f"خطأ أمر اتبع: {e}")

    async def _stop_following(self, silent: bool = False) -> None:
        self.follow_target = None
        if self.follow_task and not self.follow_task.done():
            self.follow_task.cancel()
        self.follow_task = None
        if not silent:
            msg = random.choice(STAY_MSGS)
            try:
                await self.highrise.chat(msg)
            except Exception as e:
                print(f"خطأ أمر وقوف: {e}")

    async def _follow_loop(self) -> None:
        """يتبع المستخدم كل ثانيتين"""
        while self.follow_target:
            pos = self.user_positions.get(self.follow_target)
            if pos:
                try:
                    # نمشي لنفس موقع المستخدم
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
