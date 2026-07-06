// open5gs/seed/subscribers.js
db = db.getSiblingDB("open5gs");

const subs = [
  {
    imsi: "001011234567891",
    subscribed_rau_tau_timer: 12,
    network_access_mode: 0,
    subscriber_status: 0,
    access_restriction_data: 32,
    slice: [
      {
        sst: 1,
        sd: "000001",
        default_indicator: true,
        session: [
          {
            name: "internet",
            type: 3,
            qos: {
              index: 9,
              arp: {
                priority_level: 8,
                pre_emption_capability: 1,
                pre_emption_vulnerability: 1
              }
            },
            ambr: {
              downlink: { value: 100, unit: 2 },
              uplink: { value: 50, unit: 2 }
            },
            pcc_rule: []
          }
        ]
      }
    ],
    ambr: {
      downlink: { value: 100, unit: 2 },
      uplink: { value: 50, unit: 2 }
    },
    security: {
      k: "00000000000000000000000000000000",
      amf: "8000",
      op: null,
      opc: "00000000000000000000000000000000"
    },
    schema_version: 1,
    __v: 0
  },
  {
    imsi: "001011234567892",
    subscribed_rau_tau_timer: 12,
    network_access_mode: 0,
    subscriber_status: 0,
    access_restriction_data: 32,
    slice: [
      {
        sst: 1,
        sd: "000002",
        default_indicator: true,
        session: [
          {
            name: "internet",
            type: 3,
            qos: {
              index: 2,
              arp: {
                priority_level: 8,
                pre_emption_capability: 1,
                pre_emption_vulnerability: 1
              }
            },
            ambr: {
              downlink: { value: 10, unit: 2 },
              uplink: { value: 10, unit: 2 }
            },
            pcc_rule: []
          }
        ]
      }
    ],
    ambr: {
      downlink: { value: 10, unit: 2 },
      uplink: { value: 10, unit: 2 }
    },
    security: {
      k: "00000000000000000000000000000000",
      amf: "8000",
      op: null,
      opc: "00000000000000000000000000000000"
    },
    schema_version: 1,
    __v: 0
  }
];

let upserts = 0;
for (const s of subs) {
  const res = db.subscribers.updateOne(
    { imsi: s.imsi },
    { $set: s },
    { upsert: true }
  );
  if (res.upsertedCount) upserts += 1;
}

print(`[seed] subscribers processed=${subs.length} upserts=${upserts}`);
