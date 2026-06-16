"""Client and server classes corresponding to protobuf-defined services."""
import grpc

import simulation_pb2 as simulation__pb2

class SimulationServiceStub:
    """Missing associated documentation comment in .proto file."""

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.PredictMatch = channel.unary_unary(
                '/simulation.SimulationService/PredictMatch',
                request_serializer=simulation__pb2.MatchPredictionRequest.SerializeToString,
                response_deserializer=simulation__pb2.MatchPredictionResponse.FromString,
                _registered_method=True)
        self.SimulateTournament = channel.unary_unary(
                '/simulation.SimulationService/SimulateTournament',
                request_serializer=simulation__pb2.TournamentSimulationRequest.SerializeToString,
                response_deserializer=simulation__pb2.SimulationTaskStatus.FromString,
                _registered_method=True)
        self.GetSimulationStatus = channel.unary_unary(
                '/simulation.SimulationService/GetSimulationStatus',
                request_serializer=simulation__pb2.SimulationStatusRequest.SerializeToString,
                response_deserializer=simulation__pb2.SimulationTaskStatus.FromString,
                _registered_method=True)
        self.GetFixtures = channel.unary_unary(
                '/simulation.SimulationService/GetFixtures',
                request_serializer=simulation__pb2.FixtureRequest.SerializeToString,
                response_deserializer=simulation__pb2.FixtureListResponse.FromString,
                _registered_method=True)


class SimulationServiceServicer:
    """Missing associated documentation comment in .proto file."""

    def PredictMatch(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SimulateTournament(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetSimulationStatus(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def GetFixtures(self, request, context):
        """Missing associated documentation comment in .proto file."""
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_SimulationServiceServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'PredictMatch': grpc.unary_unary_rpc_method_handler(
                    servicer.PredictMatch,
                    request_deserializer=simulation__pb2.MatchPredictionRequest.FromString,
                    response_serializer=simulation__pb2.MatchPredictionResponse.SerializeToString,
            ),
            'SimulateTournament': grpc.unary_unary_rpc_method_handler(
                    servicer.SimulateTournament,
                    request_deserializer=simulation__pb2.TournamentSimulationRequest.FromString,
                    response_serializer=simulation__pb2.SimulationTaskStatus.SerializeToString,
            ),
            'GetSimulationStatus': grpc.unary_unary_rpc_method_handler(
                    servicer.GetSimulationStatus,
                    request_deserializer=simulation__pb2.SimulationStatusRequest.FromString,
                    response_serializer=simulation__pb2.SimulationTaskStatus.SerializeToString,
            ),
            'GetFixtures': grpc.unary_unary_rpc_method_handler(
                    servicer.GetFixtures,
                    request_deserializer=simulation__pb2.FixtureRequest.FromString,
                    response_serializer=simulation__pb2.FixtureListResponse.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'simulation.SimulationService', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('simulation.SimulationService', rpc_method_handlers)


class SimulationService:
    """Missing associated documentation comment in .proto file."""

    @staticmethod
    def PredictMatch(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/simulation.SimulationService/PredictMatch',
            simulation__pb2.MatchPredictionRequest.SerializeToString,
            simulation__pb2.MatchPredictionResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def SimulateTournament(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/simulation.SimulationService/SimulateTournament',
            simulation__pb2.TournamentSimulationRequest.SerializeToString,
            simulation__pb2.SimulationTaskStatus.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def GetSimulationStatus(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/simulation.SimulationService/GetSimulationStatus',
            simulation__pb2.SimulationStatusRequest.SerializeToString,
            simulation__pb2.SimulationTaskStatus.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def GetFixtures(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/simulation.SimulationService/GetFixtures',
            simulation__pb2.FixtureRequest.SerializeToString,
            simulation__pb2.FixtureListResponse.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
