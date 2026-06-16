"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import runtime_version as _runtime_version
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder
_runtime_version.ValidateProtobufRuntimeVersion(
    _runtime_version.Domain.PUBLIC,
    6,
    33,
    5,
    '',
    'simulation.proto'
)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x10simulation.proto\x12\nsimulation\"W\n\x16MatchPredictionRequest\x12\x11\n\thome_team\x18\x01 \x01(\t\x12\x11\n\taway_team\x18\x02 \x01(\t\x12\x17\n\x0ftournament_date\x18\x03 \x01(\t\"\xf1\x01\n\x17MatchPredictionResponse\x12\x15\n\rhome_win_prob\x18\x01 \x01(\x02\x12\x15\n\raway_win_prob\x18\x02 \x01(\x02\x12\x11\n\tdraw_prob\x18\x03 \x01(\x02\x12\x1d\n\x15underdog_signal_score\x18\x04 \x01(\x02\x12\x12\n\nrisk_label\x18\x05 \x01(\t\x12 \n\x18\x65xplainability_narrative\x18\x06 \x01(\t\x12\x16\n\x0ehome_tier_form\x18\x07 \x01(\x02\x12\x16\n\x0e\x61way_tier_form\x18\x08 \x01(\x02\x12\x10\n\x08h2h_bias\x18\t \x01(\x02\"i\n\x1bTournamentSimulationRequest\x12\x17\n\x0ftournament_year\x18\x01 \x01(\x05\x12\x17\n\x0fsimulation_runs\x18\x02 \x01(\x05\x12\x18\n\x10progression_mode\x18\x03 \x01(\t\"i\n\x11TierLookbackStats\x12\x1f\n\x17trailing_point_velocity\x18\x01 \x01(\x02\x12\x1c\n\x14trailing_goal_margin\x18\x02 \x01(\x02\x12\x15\n\ropponent_tier\x18\x03 \x01(\t\")\n\x0e\x46ixtureRequest\x12\x17\n\x0ftournament_year\x18\x01 \x01(\x05\"\xdd\x02\n\x11TournamentFixture\x12\x11\n\thome_team\x18\x01 \x01(\t\x12\x11\n\taway_team\x18\x02 \x01(\t\x12\x12\n\nmatch_date\x18\x03 \x01(\t\x12\x15\n\rhome_win_prob\x18\x04 \x01(\x02\x12\x15\n\raway_win_prob\x18\x05 \x01(\x02\x12\x11\n\tdraw_prob\x18\x06 \x01(\x02\x12\x19\n\x11upset_probability\x18\x07 \x01(\x02\x12\x12\n\nrisk_label\x18\x08 \x01(\t\x12 \n\x18\x65xplainability_narrative\x18\t \x01(\t\x12\x34\n\rhome_lookback\x18\n \x01(\x0b\x32\x1d.simulation.TierLookbackStats\x12\x34\n\raway_lookback\x18\x0b \x01(\x0b\x32\x1d.simulation.TierLookbackStats\x12\x10\n\x08h2h_bias\x18\x0c \x01(\x02\"*\n\x17SimulationStatusRequest\x12\x0f\n\x07task_id\x18\x01 \x01(\t\"\xe3\x01\n\x14SimulationTaskStatus\x12\x0f\n\x07task_id\x18\x01 \x01(\t\x12\x0e\n\x06status\x18\x02 \x01(\t\x12\x11\n\tredis_key\x18\x03 \x01(\t\x12\x10\n\x08progress\x18\x04 \x01(\x02\x12<\n\x06result\x18\x05 \x03(\x0b\x32,.simulation.SimulationTaskStatus.ResultEntry\x12\x18\n\x10progression_mode\x18\x06 \x01(\t\x1a-\n\x0bResultEntry\x12\x0b\n\x03key\x18\x01 \x01(\t\x12\r\n\x05value\x18\x02 \x01(\x02:\x02\x38\x01\"F\n\x13\x46ixtureListResponse\x12/\n\x08\x66ixtures\x18\x01 \x03(\x0b\x32\x1d.simulation.TournamentFixture2\xf7\x02\n\x11SimulationService\x12W\n\x0cPredictMatch\x12\".simulation.MatchPredictionRequest\x1a#.simulation.MatchPredictionResponse\x12_\n\x12SimulateTournament\x12\'.simulation.TournamentSimulationRequest\x1a .simulation.SimulationTaskStatus\x12\\\n\x13GetSimulationStatus\x12#.simulation.SimulationStatusRequest\x1a .simulation.SimulationTaskStatus\x12J\n\x0bGetFixtures\x12\x1a.simulation.FixtureRequest\x1a\x1f.simulation.FixtureListResponseb\x06proto3')

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'simulation_pb2', _globals)
if not _descriptor._USE_C_DESCRIPTORS:
  DESCRIPTOR._loaded_options = None
  _globals['_SIMULATIONTASKSTATUS_RESULTENTRY']._loaded_options = None
  _globals['_SIMULATIONTASKSTATUS_RESULTENTRY']._serialized_options = b'8\001'
  _globals['_MATCHPREDICTIONREQUEST']._serialized_start=32
  _globals['_MATCHPREDICTIONREQUEST']._serialized_end=119
  _globals['_MATCHPREDICTIONRESPONSE']._serialized_start=122
  _globals['_MATCHPREDICTIONRESPONSE']._serialized_end=363
  _globals['_TOURNAMENTSIMULATIONREQUEST']._serialized_start=365
  _globals['_TOURNAMENTSIMULATIONREQUEST']._serialized_end=470
  _globals['_TIERLOOKBACKSTATS']._serialized_start=472
  _globals['_TIERLOOKBACKSTATS']._serialized_end=577
  _globals['_FIXTUREREQUEST']._serialized_start=579
  _globals['_FIXTUREREQUEST']._serialized_end=620
  _globals['_TOURNAMENTFIXTURE']._serialized_start=623
  _globals['_TOURNAMENTFIXTURE']._serialized_end=972
  _globals['_SIMULATIONSTATUSREQUEST']._serialized_start=974
  _globals['_SIMULATIONSTATUSREQUEST']._serialized_end=1016
  _globals['_SIMULATIONTASKSTATUS']._serialized_start=1019
  _globals['_SIMULATIONTASKSTATUS']._serialized_end=1246
  _globals['_SIMULATIONTASKSTATUS_RESULTENTRY']._serialized_start=1201
  _globals['_SIMULATIONTASKSTATUS_RESULTENTRY']._serialized_end=1246
  _globals['_FIXTURELISTRESPONSE']._serialized_start=1248
  _globals['_FIXTURELISTRESPONSE']._serialized_end=1318
  _globals['_SIMULATIONSERVICE']._serialized_start=1321
  _globals['_SIMULATIONSERVICE']._serialized_end=1696
