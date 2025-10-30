#!/usr/bin/env python3
"""
VEX API - Vulnerability Exploitability eXchange

REST API for submitting and querying VEX statements.
VEX allows organizations to override vulnerability status with ground truth.

VEX Status Values:
- not_affected: Vulnerability does not apply (risk score → 0)
- affected: Vulnerability applies and is exploitable
- fixed: Vulnerability has been patched
- under_investigation: Status being determined

API Endpoints:
- POST /api/v1/vex - Submit VEX statement
- GET /api/v1/vex/<org_id>/<cve_id> - Query VEX statements
- GET /api/v1/vex/<org_id> - Get all VEX statements for org
- DELETE /api/v1/vex/<org_id>/<cve_id>/<purl> - Retract VEX statement
"""

from flask import Flask, request, jsonify
from kafka import KafkaProducer
import json
from datetime import datetime, timezone
import argparse
from typing import Optional


app = Flask(__name__)

# Global Kafka producer (initialized in main)
producer: Optional[KafkaProducer] = None
VEX_TOPIC = 'vex-statements'


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'vex-api',
        'timestamp': datetime.now(timezone.utc).isoformat()
    })


@app.route('/api/v1/vex', methods=['POST'])
def submit_vex():
    """
    Submit VEX statement for vulnerability override.

    Request Body:
    {
      "org_id": "flox_inc",
      "cve_id": "CVE-2024-1234",
      "product_purl": "pkg:nix/nixpkgs/openssl@3.0.7",
      "status": "not_affected",  // or "affected", "fixed", "under_investigation"
      "justification": "vulnerable_code_not_in_execute_path",  // optional
      "impact_statement": "Our configuration disables the vulnerable feature",  // optional
      "action_statement": "No action required",  // optional
      "submitted_by": "security-team@flox.com"  // optional
    }

    Returns:
        202 Accepted with vex_id
    """
    vex_statement = request.json

    # Validate required fields
    required_fields = ['org_id', 'cve_id', 'product_purl', 'status']
    missing_fields = [f for f in required_fields if f not in vex_statement]

    if missing_fields:
        return jsonify({
            'error': 'Missing required fields',
            'missing': missing_fields,
            'required': required_fields
        }), 400

    # Validate status value
    valid_statuses = ['not_affected', 'affected', 'fixed', 'under_investigation']
    if vex_statement['status'] not in valid_statuses:
        return jsonify({
            'error': 'Invalid status',
            'provided': vex_statement['status'],
            'valid_values': valid_statuses
        }), 400

    # Validate PURL format (basic check)
    if not vex_statement['product_purl'].startswith('pkg:'):
        return jsonify({
            'error': 'Invalid PURL format',
            'provided': vex_statement['product_purl'],
            'expected_format': 'pkg:<type>/<namespace>/<name>@<version>'
        }), 400

    # Add metadata
    vex_statement['submitted_at'] = datetime.now(timezone.utc).isoformat()
    vex_statement['vex_version'] = '1.0'

    # Generate VEX ID (composite key: org:cve:purl)
    vex_id = f"{vex_statement['org_id']}:{vex_statement['cve_id']}:{vex_statement['product_purl']}"

    # Publish to Kafka
    try:
        if producer:
            producer.send(
                VEX_TOPIC,
                key=vex_id.encode('utf-8'),
                value=vex_statement
            )
            producer.flush()

            return jsonify({
                'status': 'accepted',
                'vex_id': vex_id,
                'message': 'VEX statement will be processed within 5 seconds',
                'details': {
                    'org_id': vex_statement['org_id'],
                    'cve_id': vex_statement['cve_id'],
                    'product_purl': vex_statement['product_purl'],
                    'vex_status': vex_statement['status'],
                    'submitted_at': vex_statement['submitted_at']
                }
            }), 202

        else:
            # Kafka producer not initialized (dev mode)
            return jsonify({
                'status': 'accepted',
                'vex_id': vex_id,
                'message': 'VEX statement received (Kafka producer offline - dev mode)',
                'details': vex_statement
            }), 202

    except Exception as e:
        return jsonify({
            'error': 'Failed to publish VEX statement',
            'message': str(e)
        }), 500


@app.route('/api/v1/vex/<org_id>/<cve_id>', methods=['GET'])
def get_vex_by_cve(org_id, cve_id):
    """
    Retrieve VEX statements for a specific org + CVE.

    Note: In production, this would query from Kafka compacted topic
    or materialized view in ClickHouse. For MVP, returns placeholder.
    """
    # TODO: Implement Kafka consumer to read from vex-statements topic
    # For now, return placeholder
    return jsonify({
        'org_id': org_id,
        'cve_id': cve_id,
        'vex_statements': [],
        'message': 'VEX query not yet implemented (requires Kafka consumer or ClickHouse)'
    }), 501


@app.route('/api/v1/vex/<org_id>', methods=['GET'])
def get_vex_by_org(org_id):
    """Retrieve all VEX statements for an organization"""
    # TODO: Implement query from materialized view
    return jsonify({
        'org_id': org_id,
        'vex_statements': [],
        'message': 'VEX query not yet implemented'
    }), 501


@app.route('/api/v1/vex/<org_id>/<cve_id>/<path:purl>', methods=['DELETE'])
def retract_vex(org_id, cve_id, purl):
    """
    Retract VEX statement by publishing tombstone.

    Tombstone (null value) triggers Kafka compaction to remove the record.
    """
    vex_id = f"{org_id}:{cve_id}:{purl}"

    try:
        if producer:
            # Send tombstone (key with null value)
            producer.send(
                VEX_TOPIC,
                key=vex_id.encode('utf-8'),
                value=None  # Tombstone
            )
            producer.flush()

            return jsonify({
                'status': 'retracted',
                'vex_id': vex_id,
                'message': 'VEX statement retracted (tombstone published)'
            }), 200

        else:
            return jsonify({
                'status': 'retracted',
                'vex_id': vex_id,
                'message': 'VEX retraction received (Kafka offline - dev mode)'
            }), 200

    except Exception as e:
        return jsonify({
            'error': 'Failed to retract VEX statement',
            'message': str(e)
        }), 500


@app.route('/api/v1/vex/schema', methods=['GET'])
def get_vex_schema():
    """Return VEX statement schema"""
    return jsonify({
        'version': '1.0',
        'schema': {
            'required_fields': {
                'org_id': 'string - Organization identifier',
                'cve_id': 'string - CVE identifier (e.g., CVE-2024-1234)',
                'product_purl': 'string - Package URL (e.g., pkg:nix/nixpkgs/openssl@3.0.7)',
                'status': 'enum - not_affected | affected | fixed | under_investigation'
            },
            'optional_fields': {
                'justification': 'string - Why this status was chosen',
                'impact_statement': 'string - Impact analysis',
                'action_statement': 'string - Required actions',
                'submitted_by': 'string - Email or identifier of submitter'
            },
            'auto_generated_fields': {
                'submitted_at': 'ISO 8601 timestamp',
                'vex_version': 'string - VEX schema version'
            }
        },
        'status_values': {
            'not_affected': 'Vulnerability does not apply to this product/configuration (risk score → 0)',
            'affected': 'Vulnerability applies and is exploitable',
            'fixed': 'Vulnerability has been patched in this version',
            'under_investigation': 'Status is being determined'
        },
        'example': {
            'org_id': 'flox_inc',
            'cve_id': 'CVE-2024-1234',
            'product_purl': 'pkg:nix/nixpkgs/openssl@3.0.7',
            'status': 'not_affected',
            'justification': 'vulnerable_code_not_in_execute_path',
            'impact_statement': 'Our configuration disables the vulnerable TLS 1.0 support',
            'action_statement': 'No action required',
            'submitted_by': 'security-team@flox.com'
        }
    })


def init_kafka_producer(bootstrap_servers):
    """Initialize Kafka producer"""
    global producer

    try:
        producer = KafkaProducer(
            bootstrap_servers=[bootstrap_servers],
            value_serializer=lambda v: json.dumps(v).encode('utf-8') if v else None,
            key_serializer=lambda k: k.encode('utf-8') if k else None
        )
        print(f"✅ Kafka producer initialized ({bootstrap_servers})")

    except Exception as e:
        print(f"⚠️  Kafka producer failed to initialize: {e}")
        print(f"   Running in dev mode (VEX statements will not be published)")
        producer = None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description='VEX API Server')

    parser.add_argument(
        '--host',
        default='0.0.0.0',
        help='Host to bind to (default: 0.0.0.0)'
    )

    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help='Port to bind to (default: 8080)'
    )

    parser.add_argument(
        '--bootstrap-servers',
        default='localhost:9092',
        help='Kafka bootstrap servers (default: localhost:9092)'
    )

    parser.add_argument(
        '--topic',
        default='vex-statements',
        help='Kafka topic for VEX statements (default: vex-statements)'
    )

    parser.add_argument(
        '--dev',
        action='store_true',
        help='Development mode (no Kafka required)'
    )

    args = parser.parse_args()

    global VEX_TOPIC
    VEX_TOPIC = args.topic

    # Initialize Kafka producer (unless in dev mode)
    if not args.dev:
        init_kafka_producer(args.bootstrap_servers)

    # Start Flask app
    print(f"🚀 Starting VEX API on {args.host}:{args.port}")
    print(f"   VEX Topic: {VEX_TOPIC}")
    print(f"   Dev Mode: {args.dev}")
    print(f"\n📖 API Documentation:")
    print(f"   POST   /api/v1/vex - Submit VEX statement")
    print(f"   GET    /api/v1/vex/<org>/<cve> - Query VEX by CVE")
    print(f"   DELETE /api/v1/vex/<org>/<cve>/<purl> - Retract VEX")
    print(f"   GET    /api/v1/vex/schema - Get VEX schema")
    print(f"   GET    /health - Health check\n")

    app.run(host=args.host, port=args.port, debug=args.dev)


if __name__ == '__main__':
    main()
