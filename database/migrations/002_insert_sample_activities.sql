-- Insert some sample activities if table is empty
-- For SQLite
INSERT OR IGNORE INTO activity_logs (type, description, created_at) VALUES
('system', 'Admin dashboard started', datetime('now', '-10 minutes')),
('user_signup', 'New user signed up - john@supplier.com', datetime('now', '-1 hour')),
('broker_approved', 'Broker approved - alex@broker.com', datetime('now', '-2 hours')),
('payout', 'Payout processed - $500 to broker', datetime('now', '-3 hours')),
('payment', 'Payment received - $299 from lumberyard.com', datetime('now', '-4 hours')),
('calculation', '10 calculations from IP 192.168.1.1', datetime('now', '-5 hours'));

-- For PostgreSQL (run separately if using PostgreSQL)
-- INSERT INTO activity_logs (type, description, created_at) VALUES
-- ('system', 'Admin dashboard started', NOW() - INTERVAL '10 minutes'),
-- ('user_signup', 'New user signed up - john@supplier.com', NOW() - INTERVAL '1 hour'),
-- ('broker_approved', 'Broker approved - alex@broker.com', NOW() - INTERVAL '2 hours'),
-- ('payout', 'Payout processed - $500 to broker', NOW() - INTERVAL '3 hours'),
-- ('payment', 'Payment received - $299 from lumberyard.com', NOW() - INTERVAL '4 hours'),
-- ('calculation', '10 calculations from IP 192.168.1.1', NOW() - INTERVAL '5 hours')
-- ON CONFLICT DO NOTHING;

