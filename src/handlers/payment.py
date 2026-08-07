"""Payment handlers: tariffs, Telegram Stars, promocodes."""
from aiogram import F
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery
from aiogram.fsm.context import FSMContext

from src.keyboards import get_tariffs_menu, get_back_button
from src.data.tariffs import PLANS, get_plan
from src.core.config import config

from .common import router, get_db, PromoState


@router.callback_query(F.data == "tariffs")
async def cb_tariffs(call: CallbackQuery):
    await call.answer()
    text_lines = ["💳 <b>Тарифные планы</b>\n"]
    for plan in PLANS.values():
        text_lines.append(
            f"{plan.name}\n"
            f"  └ {plan.description}\n"
            f"  └ Цена: <b>{plan.price_stars}⭐</b> ({plan.duration_days} дней)\n"
        )
    text_lines.append("\n<i>Оплата через Telegram Stars (XTR)</i>")
    await call.message.edit_text(
        "\n".join(text_lines),
        reply_markup=get_tariffs_menu(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("buy_plan_"))
async def cb_buy_plan(call: CallbackQuery):
    await call.answer()
    plan_key = call.data.replace("buy_plan_", "")
    plan = PLANS.get(plan_key)
    if not plan:
        return

    prices = [LabeledPrice(label=f"{plan.name} ({plan.duration_days} дней)", amount=plan.price_stars)]
    await call.bot.send_invoice(
        chat_id=call.from_user.id,
        title=f"Подписка Kufar Online — {plan.name}",
        description=plan.description,
        payload=f"subscription_{plan_key}_{plan.duration_days}days",
        provider_token="",
        currency="XTR",
        prices=prices,
        start_parameter="pay_sub"
    )


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    if len(parts) >= 3 and parts[0] == "subscription":
        plan_key = parts[1]
        days_str = parts[2].replace("days", "")
        try:
            days = int(days_str)
        except ValueError:
            days = 30

        user_id = message.from_user.id
        await get_db().give_subscription_by_identifier(str(user_id), days)
        await get_db().set_tariff_plan(user_id, plan_key)
        plan = get_plan(plan_key)
        await message.answer(
            f"🎉 <b>Оплата прошла!</b>\n\n💎 Тариф <b>{plan.name}</b> активирован на <b>{days} дней</b>.",
            reply_markup=get_back_button("main_menu"),
            parse_mode="HTML"
        )


# ── Promocodes ─────────────────────────────────────

@router.callback_query(F.data == "promo_menu")
async def cb_promo_menu(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(PromoState.waiting_for_code)
    await call.message.edit_text(
        "🎟 <b>Промокод</b>\n\nВведите ваш промокод:",
        reply_markup=get_back_button(),
        parse_mode="HTML"
    )


@router.message(PromoState.waiting_for_code)
async def process_promo_code(message: Message, state: FSMContext):
    code = message.text.strip()
    if not code:
        await message.answer("❌ Введите непустой промокод.")
        return

    success, msg = await get_db().redeem_promocode(code, message.from_user.id)
    await state.clear()
    await message.answer(
        f"{'✅' if success else '❌'} {msg}",
        reply_markup=get_back_button(),
        parse_mode="HTML"
    )
