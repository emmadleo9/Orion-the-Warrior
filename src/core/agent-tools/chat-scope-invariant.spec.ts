import type { z } from 'zod';
import { allAgentTools } from './tools';
import type { AnyToolDescriptor } from './tool-descriptor';

// The MCP half of the chat fence, pinned the way the REST marks are in
// modules/auth/chat-scope-coverage.spec.ts (MUST_STAY_MARKED, MUST_STAY_UNMARKED, AGNOSTIC_GRANTS).
//
// tool-invoker refuses a chat-restricted key on every tool without a chatScope mark and trusts the
// mark of any tool that has one: 'agnostic' skips every chat check, 'filtered' skips the field check,
// and an array checks only the fields it names. A lost mark therefore becomes a quiet refusal, while a
// wrong 'agnostic' or 'filtered' mark, or an array that misses a chat field, lets a restricted key act
// on a chat outside its allowlist with every other spec still green.
describe('agent-tool registry: chatScope marks', () => {
  // Handlers are never invoked here; stub services are fine, only the declarations are inspected.
  const tools: AnyToolDescriptor[] = [...allAgentTools({} as never)];
  const names = (list: AnyToolDescriptor[]): string[] => list.map(tool => tool.name).sort();

  /** Input fields that name a chat the invoker has to check. */
  const CHAT_FIELDS = ['chatId', 'fromChatId', 'toChatId', 'contactId', 'groupId'];
  const chatFieldsOf = (tool: AnyToolDescriptor): string[] =>
    Object.keys((tool.inputSchema as unknown as z.ZodObject<Record<string, z.ZodType>>).shape ?? {}).filter(field =>
      CHAT_FIELDS.includes(field),
    );

  /**
   * The complete set granted 'agnostic'. Each entry is a deliberate access decision, so the spec fails
   * if a grant is missing from here OR listed here without the mark.
   */
  const AGNOSTIC = [
    // Reports the session's own state and account: no chat data, changes nothing.
    'SessionFindOne',
  ];

  /** The complete set marked 'filtered': each handler narrows a chat-typed result to the key's chats. */
  const FILTERED = ['ContactFindAll', 'GroupFindAll', 'LabelListChats', 'SessionGetChats'];

  /**
   * Tools that name a chat yet must stay UNMARKED, so a restricted key keeps being refused. They would
   * pass the field check below if marked, which is why they are pinned.
   */
  const MUST_STAY_UNMARKED = [
    // Adding a participant can DM them an invite, a chat no input field names.
    'GroupAddParticipants',
    // An invite link admits anyone who holds it, and keeps working after the key is revoked.
    'GroupGetInviteCode',
  ];

  it('grants the agnostic mark to exactly the listed tools', () => {
    expect(names(tools.filter(tool => tool.chatScope === 'agnostic'))).toEqual(AGNOSTIC);
  });

  it('grants the filtered mark to exactly the listed tools', () => {
    expect(names(tools.filter(tool => tool.chatScope === 'filtered'))).toEqual(FILTERED);
  });

  it('leaves the chat-taking tools that must stay closed unmarked', () => {
    const closed = tools.filter(tool => MUST_STAY_UNMARKED.includes(tool.name));
    // Guard the guard: a renamed tool would otherwise drop out of the list without a failure.
    expect(names(closed)).toEqual(MUST_STAY_UNMARKED);
    expect(closed.filter(tool => chatFieldsOf(tool).length === 0)).toEqual([]);
    expect(names(closed.filter(tool => tool.chatScope !== undefined))).toEqual([]);
  });

  it('fences every chat field of every other tool that takes one', () => {
    const taking = tools.filter(tool => !MUST_STAY_UNMARKED.includes(tool.name) && chatFieldsOf(tool).length > 0);
    // Guard the guard: a field probe that matched nothing would make this vacuous.
    expect(taking.length).toBeGreaterThan(0);
    const unfenced = taking.filter(tool => {
      const mark = tool.chatScope;
      return !Array.isArray(mark) || !chatFieldsOf(tool).every(field => mark.includes(field));
    });
    expect(names(unfenced)).toEqual([]);
  });
});
