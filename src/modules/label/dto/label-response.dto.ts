import { ApiProperty } from '@nestjs/swagger';

/**
 * Response shapes for the label routes. These describe what the handlers already return — the
 * payload is the raw handler value, not an envelope.
 *
 * Decorated properties avoid named utility types: emitDecoratorMetadata wraps a named type in a
 * runtime guard whose other arm can never execute, leaving an uncoverable branch.
 */
export class LabelDto {
  @ApiProperty({ description: 'Label id, assigned by WhatsApp.', example: '1' })
  id!: string;

  @ApiProperty({ description: 'Label text.', example: 'Paid' })
  name!: string;

  @ApiProperty({
    description:
      'Display colour as hex. The write path takes a colour INDEX (0-19) instead — neither engine ' +
      'exposes the index-to-hex mapping, so the two directions deliberately differ.',
    example: '#5bc0de',
  })
  hexColor!: string;
}

export class LabelAckResponseDto {
  @ApiProperty({ description: 'Always true — a failure is reported as a non-2xx status, not as false.', example: true })
  success!: boolean;
}
