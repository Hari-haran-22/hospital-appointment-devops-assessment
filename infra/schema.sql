CREATE TABLE IF NOT EXISTS doctors (
    id text PRIMARY KEY,
    name text NOT NULL,
    specialty text NOT NULL,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS patients (
    id text PRIMARY KEY,
    display_name text NOT NULL,
    active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS appointments (
    id uuid PRIMARY KEY,
    patient_id text NOT NULL REFERENCES patients(id),
    doctor_id text NOT NULL REFERENCES doctors(id),
    start_at timestamptz NOT NULL,
    status text NOT NULL DEFAULT 'confirmed' CHECK (status IN ('confirmed', 'cancelled')),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS one_confirmed_appointment_per_doctor_slot
    ON appointments (doctor_id, start_at) WHERE status = 'confirmed';

CREATE TABLE IF NOT EXISTS audit_events (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    action text NOT NULL CHECK (action IN ('created', 'rescheduled', 'cancelled')),
    actor_role text NOT NULL CHECK (actor_role IN ('patient', 'staff')),
    actor_id text,
    appointment_id uuid NOT NULL REFERENCES appointments(id),
    created_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO doctors (id, name, specialty) VALUES
    ('D001', 'Dr Asha Rao', 'General Medicine'),
    ('D002', 'Dr Vikram Shah', 'Cardiology')
ON CONFLICT (id) DO NOTHING;

INSERT INTO patients (id, display_name) VALUES
    ('P001', 'Synthetic Patient One'),
    ('P002', 'Synthetic Patient Two')
ON CONFLICT (id) DO NOTHING;

GRANT CONNECT ON DATABASE :"db_name" TO appointment_app;
GRANT USAGE ON SCHEMA public TO appointment_app;
GRANT SELECT ON doctors, patients TO appointment_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON appointments, audit_events TO appointment_app;
GRANT USAGE, SELECT ON SEQUENCE audit_events_id_seq TO appointment_app;
