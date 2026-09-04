import { IParser } from './IParser';
import { KufarParser } from './KufarParser';
import { OnlinerParser } from './OnlinerParser';
import { AvParser } from './AvParser';
import { Platform } from '../types';

export class ParserFactory {
  private static parsers: Map<Platform, IParser> = new Map<Platform, IParser>([
    ['kufar', new KufarParser()],
    ['onliner', new OnlinerParser()],
    ['av', new AvParser()],
  ]);

  static getParser(platform: Platform): IParser | null {
    return this.parsers.get(platform) || null;
  }
}
