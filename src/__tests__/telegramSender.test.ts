import { TelegramSender } from '../services/TelegramSender';
import { FormattedAd } from '../services/AdPresenter';

class FakeBot {
  sendMessage = jest.fn(async () => ({}));
  sendPhoto = jest.fn(async () => ({}));
  sendMediaGroup = jest.fn(async () => []);
  sendVenue = jest.fn(async () => ({}));
}

function makeAd(media: string[] = []): FormattedAd {
  return { text: 'test ad', media };
}

describe('TelegramSender', () => {
  test('sends photo with caption for a single image', async () => {
    const bot = new FakeBot();
    const sender = new TelegramSender(bot as any);

    await sender.send(123, makeAd(['http://img/1']));

    // Теперь все фото (даже 1) отправляются через media group, первое фото с caption
    expect(bot.sendMediaGroup).toHaveBeenCalledWith(123, [
      { type: 'photo', media: 'http://img/1', caption: 'test ad' },
    ]);
    expect(bot.sendPhoto).not.toHaveBeenCalled();
    expect(bot.sendMessage).not.toHaveBeenCalled();
  });

  test('sends media group when there are several photos', async () => {
    const bot = new FakeBot();
    const sender = new TelegramSender(bot as any);

    await sender.send(123, makeAd(['http://img/1', 'http://img/2']));

    expect(bot.sendMediaGroup).toHaveBeenCalledWith(123, [
      { type: 'photo', media: 'http://img/1', caption: 'test ad' },
      { type: 'photo', media: 'http://img/2' },
    ]);
    expect(bot.sendPhoto).not.toHaveBeenCalled();
  });

  test('sends just text when no media', async () => {
    const bot = new FakeBot();
    const sender = new TelegramSender(bot as any);

    await sender.send(123, makeAd([]));

    expect(bot.sendMessage).toHaveBeenCalledWith(123, 'test ad', { parse_mode: 'HTML' });
    expect(bot.sendPhoto).not.toHaveBeenCalled();
    expect(bot.sendMediaGroup).not.toHaveBeenCalled();
  });

  test('falls back to a single photo when sendMediaGroup fails', async () => {
    const bot = new FakeBot();
    bot.sendMediaGroup.mockRejectedValueOnce(new Error('bad request'));
    const sender = new TelegramSender(bot as any);

    await sender.send(123, makeAd(['http://img/1', 'http://img/2']));

    expect(bot.sendMediaGroup).toHaveBeenCalledTimes(1);
    expect(bot.sendPhoto).toHaveBeenCalledWith(123, 'http://img/1', { caption: 'test ad', parse_mode: 'HTML' });
  });

  test('sendBatch sends all messages sequentially', async () => {
    const bot = new FakeBot();
    const sender = new TelegramSender(bot as any);

    await sender.sendBatch(123, [makeAd(['http://img/1']), makeAd(['http://img/2'])]);

    // sendBatch использует send() → sendMediaGroup для каждого
    expect(bot.sendMediaGroup).toHaveBeenCalledTimes(2);
    expect(bot.sendPhoto).not.toHaveBeenCalled();
  });
});
