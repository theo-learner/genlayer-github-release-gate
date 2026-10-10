# Studio integration evidence

Observed 2026-10-10 in GenLayer Studio (hosted simulator, not a production/testnet deployment).

- Mode: Normal (Full Consensus), Simulation Mode unchecked.
- Built-in Studio account: 0x3Aa327881F1f70978A6A3d6aB385593b61Cc5496. Portal-linked external wallet did not produce a transaction, so the built-in account was used for this simulator test.
- Contract: https://explorer-studio.genlayer.com/address/0x2D86c8496E254b2388189a89dd232B2EA3eBf2B9
- Deployment transaction (FINALIZED): 0xbb6825af559bf1cfebe5fd61764b6bf1baf13f7b215af4a06c2542cf7bed78c0
- verify_release transaction (FINALIZED): 0xbe94a5296a086ce5cca16c0decf13ac6469b888804a0373f668ae5c01ba6951a
- get_policy at Finalized state returned check_count=1, status=READY, expected_sha=observed_sha=0e322af87745eff34caffe4df68456ebc20d9068, owner=psf, repo=requests, tag=v2.32.3.
- Source fixture: https://github.com/psf/requests/releases/tag/v2.32.3

An earlier draft used the incorrect Response.status_code attribute. Its finalized verification transaction returned an execution error and left PENDING. It is not evidence of a successful verification. The submitted source uses Response.status and the deployment above is the corrected version.

Studio URLs/state may be reset by the hosted service. Unit tests are independently reproducible, but mocked tests are not consensus evidence.
