from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from uuid import uuid4

import grpc
from grpc_reflection.v1alpha import reflection

import log
import rides_pb2 as pb
import rides_pb2_grpc as rpc
import validate


def new_ride_id():
    return uuid4().hex


class TimingInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        start = perf_counter()
        try:
            return continuation(handler_call_details)
        finally:
            duration = perf_counter() - start
            name = handler_call_details.method
            log.info(f'{name} took {duration:.3f}sec')


class Rides(rpc.RidesServicer):
    def Start(self, request, context):
        log.info(f'ride: {repr(request)}')

        try:
            validate.start_request(request)
        except validate.Error as err:
            log.error(f'bad request: {err}')
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            context.set_details(f'{err.field} is {err.reason}')
            raise err

        # TODO: store ride in DB
        ride_id = new_ride_id()
        return pb.StartResponse(id=ride_id)

    def Track(self, request_interator, context):
        count = 0
        for request in request_interator:
            # TODO: store in DB
            log.info(f'track: {request}')
            count += 1

        return pb.TrackResponse(count=count)


def load_credentials():
    with open(config.cert_file, 'rb') as fp:
        cert = fp.read()

    with open(config.key_file, 'rb') as fp:
        key = fp.read()

    return grpc.ssl_server_credentials([(key, cert)])


def build_server(port):
    server = grpc.server(ThreadPoolExecutor())
    rpc.add_RidesServicer_to_server(Rides(), server)

    names = (
        pb.DESCRIPTOR.services_by_name['Rides'].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(names, server)
    addr = f'[::]:{port}'
    server.add_insecure_port(addr)
    return server


if __name__ == '__main__':
    import config

    server = grpc.server(
        ThreadPoolExecutor(),
        interceptors=[TimingInterceptor()]
    )
    rpc.add_RidesServicer_to_server(Rides(), server)
    names = (
        pb.DESCRIPTOR.services_by_name['Rides'].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(names, server)

    addr = f'[::]:{config.port}'
    credentials = load_credentials()
    server.add_secure_port(addr, credentials)
    server.start()

    log.info(f'server ready on {addr}')
    server.wait_for_termination()
