import { LinkAcceptance } from '../utils/linkAcceptance';

describe('LinkAcceptance.assess', () => {
  describe('kufar', () => {
    test('accepts /l/ search page', () => {
      expect(LinkAcceptance.assess('https://www.kufar.by/l/r~minsk/muzykalnye-instrumenty')).toEqual({
        platform: 'kufar',
        ok: true,
      });
    });

    test('accepts /re/ real-estate search page', () => {
      expect(LinkAcceptance.assess('https://re.kufar.by/l/minsk/snyat/kvartiru')).toEqual({
        platform: 'kufar',
        ok: true,
      });
    });

    test('rejects single ad link on kufar', () => {
      const result = LinkAcceptance.assess('https://www.kufar.by/item/1234567');
      expect(result.platform).toBe('kufar');
      expect(result.ok).toBe(false);
      expect(result.reason).toBeDefined();
    });
  });

  describe('onliner', () => {
    test('accepts baraholka hostname', () => {
      expect(LinkAcceptance.assess('https://baraholka.onliner.by/category')).toEqual({
        platform: 'onliner',
        ok: true,
      });
    });

    test('accepts ab.onliner hostname', () => {
      expect(LinkAcceptance.assess('https://ab.onliner.by/cars')).toEqual({
        platform: 'onliner',
        ok: true,
      });
    });

    test('accepts r.onliner hostname', () => {
      expect(LinkAcceptance.assess('https://r.onliner.by/ak/')).toEqual({
        platform: 'onliner',
        ok: true,
      });
    });

    test('rejects onliner single ad / unsupported page', () => {
      const result = LinkAcceptance.assess('https://www.onliner.by/catalog');
      expect(result.platform).toBe('onliner');
      expect(result.ok).toBe(false);
      expect(result.reason).toBeDefined();
    });
  });

  describe('av', () => {
    test('accepts av.by hostname', () => {
      expect(LinkAcceptance.assess('https://cars.av.by/filter')).toEqual({
        platform: 'av',
        ok: true,
      });
    });

    test('rejects non-av.by subdomains', () => {
      const result = LinkAcceptance.assess('https://myavby-example.com/items');
      expect(result.ok).toBe(false);
      expect(result.platform).toBeNull();
    });
  });

  describe('invalid and unsupported', () => {
    test('rejects non-URL', () => {
      const result = LinkAcceptance.assess('not a url');
      expect(result.ok).toBe(false);
      expect(result.platform).toBeNull();
    });

    test('rejects unsupported platform', () => {
      const result = LinkAcceptance.assess('https://example.com/items');
      expect(result.ok).toBe(false);
      expect(result.platform).toBeNull();
      expect(result.reason).toBeDefined();
    });

    test('rejects onliner main site', () => {
      const result = LinkAcceptance.assess('https://www.onliner.by/');
      expect(result.ok).toBe(false);
      expect(result.platform).toBe('onliner');
    });

    test('rejects kufar single ad', () => {
      const result = LinkAcceptance.assess('https://www.kufar.by/item/123456');
      expect(result.ok).toBe(false);
      expect(result.platform).toBe('kufar');
    });
  });
});
