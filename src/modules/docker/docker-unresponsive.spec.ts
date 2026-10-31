import * as net from 'net';
import type { AddressInfo } from 'net';
import { DockerService } from './docker.service';

/**
 * dockerode sets no timeout. A daemon or socket proxy that accepts the connection and never answers
 * (a firewall dropping packets, a wedged upstream behind docker-socket-proxy) must read as "Docker not
 * available" rather than hold the boot that awaits the ping.
 */
describe('DockerService against a daemon that never answers', () => {
  const sockets = new Set<net.Socket>();
  let server: net.Server;
  let previousHost: string | undefined;

  beforeEach(async () => {
    previousHost = process.env.DOCKER_HOST;
    server = net.createServer(socket => {
      sockets.add(socket);
      socket.on('data', () => undefined);
      socket.on('close', () => sockets.delete(socket));
    });
    await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
    process.env.DOCKER_HOST = `tcp://127.0.0.1:${(server.address() as AddressInfo).port}`;
  });

  afterEach(async () => {
    if (previousHost === undefined) delete process.env.DOCKER_HOST;
    else process.env.DOCKER_HOST = previousHost;
    for (const socket of sockets) socket.destroy();
    await new Promise<void>(resolve => server.close(() => resolve()));
  });

  it('boots with Docker unavailable once the ping is not answered in time', async () => {
    const service = new DockerService();
    service.callTimeoutMs = 150;

    const started = Date.now();
    await service.onModuleInit();

    expect(Date.now() - started).toBeLessThan(2000);
    expect(service.isDockerAvailable()).toBe(false);
  }, 10_000);

  // A call that is only raced against its deadline keeps its request and its socket, and every later
  // availability check starts another one, until the process runs out of descriptors.
  it('closes the connection of every call it gave up on', async () => {
    const service = new DockerService();
    service.callTimeoutMs = 100;
    await service.onModuleInit();

    for (let i = 0; i < 6; i++) {
      service.isDockerAvailable();
      await new Promise(resolve => setTimeout(resolve, 150));
    }
    await new Promise(resolve => setTimeout(resolve, 200));

    expect(sockets.size).toBeLessThanOrEqual(1);
  }, 15_000);
});
