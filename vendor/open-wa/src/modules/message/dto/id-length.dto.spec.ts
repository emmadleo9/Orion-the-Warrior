import { DECORATORS } from '@nestjs/swagger';
import { plainToInstance } from 'class-transformer';
import { validate, type ValidationError } from 'class-validator';
import {
  ClickButtonDto,
  DeleteMessageDto,
  EditMessageDto,
  ForwardMessageDto,
  PinMessageDto,
  ReactMessageDto,
  ReplyMessageDto,
  SendContactDto,
  SendLocationDto,
  SendPollDto,
  StarMessageDto,
  UnpinMessageDto,
  VotePollDto,
} from './message-actions.dto';
import { SendBulkMessageDto } from './bulk-message.dto';
import {
  BATCH_ID_MAX_LENGTH,
  CHAT_ID_MAX_LENGTH,
  SendAudioMessageDto,
  SendMediaMessageDto,
  SendTextMessageDto,
} from './send-message.dto';
import { SendTemplateMessageDto } from './send-template.dto';

// A chat id and a batch id are stored under btree indexes, and PostgreSQL refuses an index entry past
// about 2.7 KB, which the client then saw as a 500. The REST bodies refuse them as a 400 first, and
// publish the bound so a client generated from the schema knows it.
const fields: Array<[string, new () => object, string, number]> = [
  ['SendTextMessageDto', SendTextMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendMediaMessageDto', SendMediaMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendAudioMessageDto', SendAudioMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendLocationDto', SendLocationDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendContactDto', SendContactDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendPollDto', SendPollDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendTemplateMessageDto', SendTemplateMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['ReplyMessageDto', ReplyMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['ForwardMessageDto', ForwardMessageDto, 'fromChatId', CHAT_ID_MAX_LENGTH],
  ['ForwardMessageDto', ForwardMessageDto, 'toChatId', CHAT_ID_MAX_LENGTH],
  ['ReactMessageDto', ReactMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['DeleteMessageDto', DeleteMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['PinMessageDto', PinMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['UnpinMessageDto', UnpinMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['StarMessageDto', StarMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['EditMessageDto', EditMessageDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['VotePollDto', VotePollDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['ClickButtonDto', ClickButtonDto, 'chatId', CHAT_ID_MAX_LENGTH],
  ['SendBulkMessageDto', SendBulkMessageDto, 'batchId', BATCH_ID_MAX_LENGTH],
];

describe('caller-chosen id length caps', () => {
  // Only the property under test is read: the other required fields of each body are left out on purpose.
  const constraintsOf = async (dto: new () => object, field: string, value: string) => {
    const errors = await validate(plainToInstance(dto, { [field]: value }, { enableImplicitConversion: true }));
    return errors.find(error => error.property === field)?.constraints;
  };

  it.each(fields)('%s.%s accepts the cap and refuses one more character', async (_name, dto, field, max) => {
    expect((await constraintsOf(dto, field, 'a'.repeat(max)))?.maxLength).toBeUndefined();
    expect((await constraintsOf(dto, field, 'a'.repeat(max + 1)))?.maxLength).toEqual(
      expect.stringContaining(String(max)),
    );
  });

  // The bulk item class is not exported, so it is reached through the body that holds the list.
  it('caps the chat id of every bulk item, where most ids arrive', async () => {
    const flatten = (errors: ValidationError[], prefix = ''): Array<[string, ValidationError['constraints']]> =>
      errors.flatMap(error => [
        [prefix + error.property, error.constraints],
        ...flatten(error.children ?? [], `${prefix}${error.property}.`),
      ]);
    const refused = async (chatId: string): Promise<boolean> => {
      const body = plainToInstance(SendBulkMessageDto, { messages: [{ chatId }] }, { enableImplicitConversion: true });
      const found = flatten(await validate(body)).find(([path]) => path === 'messages.0.chatId');
      return found?.[1]?.maxLength !== undefined;
    };

    expect(await refused('a'.repeat(CHAT_ID_MAX_LENGTH))).toBe(false);
    expect(await refused('a'.repeat(CHAT_ID_MAX_LENGTH + 1))).toBe(true);
  });

  it.each(fields)('%s.%s publishes the cap in the schema', (_name, dto, field, max) => {
    const published = Reflect.getMetadata(DECORATORS.API_MODEL_PROPERTIES, dto.prototype as object, field) as
      { maxLength?: number } | undefined;
    expect(published?.maxLength).toBe(max);
  });
});
