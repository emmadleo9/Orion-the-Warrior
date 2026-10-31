import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { WebhookOutboxEvent } from './entities/webhook-outbox-event.entity';
import { WebhookOutboxService } from './webhook-outbox.service';

/**
 * The one owner of WebhookOutboxService, which both WebhookModule and QueueModule need. QueueModule
 * cannot import WebhookModule (WebhookModule imports it), and providing the service in each made two
 * instances: the startup prune and the daily prune timer ran twice.
 */
@Module({
  imports: [TypeOrmModule.forFeature([WebhookOutboxEvent], 'data')],
  providers: [WebhookOutboxService],
  exports: [WebhookOutboxService],
})
export class WebhookOutboxModule {}
