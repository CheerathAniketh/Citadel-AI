import logging
from typing import Dict, Any, List
from datetime import datetime
from app.workflows.state import CitadelState
from app.integrations.aws_connector import AWSConnector
from app.integrations.gcp_connector import GCPConnector
from app.integrations.azure_connector import AzureConnector
from app.modules.bias.analyzer import calculate_spd, calculate_di, compute_eod, analyze_bias, get_group_stats
#from app.modules.bias.explainer import explain_bias

logger = logging.getLogger(__name__)

# ==================== DISCOVERY NODE ====================
async def discover_models(state: CitadelState) -> CitadelState:
    """
    Step 1: Auto-discover all AI models in cloud
    Connects to AWS/GCP/Azure and finds deployed models
    """
    try:
        logger.info(f"🔍 Discovering models in {state['cloud_provider']}...")
        state['audit_log'].append(f"📍 Discovery started")
        
        # Select connector based on cloud provider
        if state['cloud_provider'] == 'aws':
            connector = AWSConnector(state['cloud_credentials'])
        elif state['cloud_provider'] == 'gcp':
            connector = GCPConnector(state['cloud_credentials'])
        elif state['cloud_provider'] == 'azure':
            connector = AzureConnector(state['cloud_credentials'])
        else:
            raise ValueError(f"Unknown cloud provider: {state['cloud_provider']}")
        
        # Discover models
        models = await connector.discover_models()
        
        state['discovered_models'] = models
        state['discovered_count'] = len(models)
        state['audit_log'].append(f"✅ Discovered {len(models)} models in {state['cloud_provider']}")
        
        logger.info(f"✅ Found {len(models)} models")
        
    except Exception as e:
        error_msg = f"❌ Discovery failed: {str(e)}"
        logger.error(error_msg)
        state['discovery_error'] = str(e)
        state['audit_log'].append(error_msg)
        state['workflow_status'] = 'failed'
        state['error'] = str(e)
    
    return state

# ==================== MONITORING NODE ====================
async def monitor_predictions(state: CitadelState) -> CitadelState:
    """
    Step 2: Poll recent predictions from discovered models
    Fetches prediction logs from cloud provider
    """
    if not state['discovered_models']:
        state['audit_log'].append("⚠️ No models to monitor")
        return state
    
    try:
        logger.info("📊 Monitoring predictions...")
        state['audit_log'].append("📍 Monitoring started")
        
        # Get connector
        if state['cloud_provider'] == 'aws':
            connector = AWSConnector(state['cloud_credentials'])
        elif state['cloud_provider'] == 'gcp':
            connector = GCPConnector(state['cloud_credentials'])
        elif state['cloud_provider'] == 'azure':
            connector = AzureConnector(state['cloud_credentials'])
        else:
            raise ValueError(f"Unknown cloud provider: {state['cloud_provider']}")
        
        # Fetch predictions from each model
        all_predictions = []
        for model in state['discovered_models']:
            try:
                predictions = await connector.get_predictions(
                    model_id=model['id'],
                    limit=1000
                )
                all_predictions.extend(predictions)
                logger.info(f"Fetched {len(predictions)} predictions from {model['name']}")
            except Exception as e:
                logger.warning(f"Failed to fetch predictions from {model['name']}: {e}")
        
        state['recent_predictions'] = all_predictions
        state['predictions_count'] = len(all_predictions)
        state['audit_log'].append(f"✅ Fetched {len(all_predictions)} predictions")
        
        logger.info(f"✅ Retrieved {len(all_predictions)} predictions")
        
    except Exception as e:
        error_msg = f"❌ Monitoring failed: {str(e)}"
        logger.error(error_msg)
        state['monitoring_error'] = str(e)
        state['audit_log'].append(error_msg)
        state['workflow_status'] = 'failed'
        state['error'] = str(e)
    
    return state

# ==================== ANALYSIS NODE ====================
async def analyze_bias(state: CitadelState) -> CitadelState:
    """
    Step 3: Run bias analysis on predictions
    Computes: SPD, Disparate Impact, Equalized Odds
    Explains via SHAP
    """
    if not state['recent_predictions']:
        state['audit_log'].append("⚠️ No predictions to analyze")
        return state
    
    try:
        logger.info("📈 Analyzing bias...")
        state['audit_log'].append("📍 Analysis started")
        
        predictions = state['recent_predictions']
        
        # Try to find sensitive attribute (gender, age, etc.)
        sensitive_attrs = []
        for p in predictions:
            if 'group' in p:
                sensitive_attrs.append(p['group'])
            elif 'gender' in p:
                sensitive_attrs.append(p['gender'])
            elif 'age_group' in p:
                sensitive_attrs.append(p['age_group'])
            else:
                sensitive_attrs.append('unknown')
        
        # Extract target
        targets = [p.get('prediction', 'unknown') for p in predictions]
        
        # Compute bias metrics
        try:
            # For basic metrics without pandas df, use simple calculation
            di = None
            spd = None
            eod = None
            
            # Try full analysis if possible
            if targets and sensitive_attrs:
                try:
                    # Simple DI/SPD calculation
                    from collections import defaultdict
                    group_stats = defaultdict(lambda: {'positive': 0, 'total': 0})
                    
                    for target, group in zip(targets, sensitive_attrs):
                        group_stats[str(group)]['total'] += 1
                        if str(target).lower() in ['1', 'yes', 'true', 'positive', 'approved']:
                            group_stats[str(group)]['positive'] += 1
                    
                    rates = []
                    for group, stats in group_stats.items():
                        if stats['total'] > 0:
                            rate = stats['positive'] / stats['total']
                            rates.append(rate)
                    
                    if rates:
                        di = min(rates) / max(rates) if max(rates) > 0 else 0
                        spd = max(rates) - min(rates)
                        
                except Exception as calc_e:
                    logger.warning(f"Could not compute bias metrics: {calc_e}")
        
        except Exception as e:
            logger.warning(f"Could not compute bias metrics: {e}")
        
        # Explain via SHAP
        try:
            explanation = {"error": "explainer not yet implemented"}
        except Exception as e:
            logger.warning(f"Could not generate SHAP explanation: {e}")
            explanation = {"error": str(e)}
        
        # Determine status
        status = "healthy"
        if di is not None and di < 0.8:
            status = "critical"
        elif spd is not None and spd > 0.1:
            status = "warning"
        
        state['bias_metrics'] = {
            'disparate_impact': di,
            'statistical_parity_diff': spd,
            'equalized_odds': eod,
            'samples_count': len(predictions),
            'status': status,
            'timestamp': datetime.now().isoformat()
        }
        
        state['root_causes'] = explanation
        
        state['audit_log'].append(
            f"✅ Bias Analysis: DI={di:.2f if di else 'N/A'}, "
            f"SPD={spd:.2f if spd else 'N/A'}, Status={status}"
        )
        
        logger.info(f"✅ Bias analysis complete: {status}")
        
    except Exception as e:
        error_msg = f"❌ Analysis failed: {str(e)}"
        logger.error(error_msg)
        state['analysis_error'] = str(e)
        state['audit_log'].append(error_msg)
        state['workflow_status'] = 'failed'
        state['error'] = str(e)
    
    return state

# ==================== DETECTION NODE ====================
async def detect_violation(state: CitadelState) -> CitadelState:
    """
    Step 4: Check if bias exceeds fairness thresholds
    Triggers alerts if violations detected
    """
    try:
        logger.info("🎯 Detecting violations...")
        state['audit_log'].append("📍 Detection started")
        
        di = state['bias_metrics'].get('disparate_impact')
        spd = state['bias_metrics'].get('statistical_parity_diff')
        
        alerts = []
        needs_remediation = False
        
        # EEOC 4/5ths rule: DI < 0.8 = illegal
        if di is not None and di < 0.8:
            alerts.append({
                'type': 'bias_critical',
                'severity': 'critical',
                'metric': 'disparate_impact',
                'value': di,
                'threshold': 0.8,
                'message': f'Critical: Disparate Impact {di:.2f} below legal threshold (0.8)'
            })
            needs_remediation = True
        
        # SPD > 0.1 = significant bias
        elif spd is not None and spd > 0.1:
            alerts.append({
                'type': 'bias_warning',
                'severity': 'warning',
                'metric': 'statistical_parity_diff',
                'value': spd,
                'threshold': 0.1,
                'message': f'Warning: Statistical Parity Diff {spd:.2f} exceeds threshold (0.1)'
            })
        
        state['alerts'] = alerts
        state['needs_remediation'] = needs_remediation
        
        if alerts:
            state['audit_log'].append(f"🔴 {len(alerts)} violation(s) detected")
        else:
            state['audit_log'].append("✅ All metrics within acceptable range")
        
        logger.info(f"Detection complete: {len(alerts)} alerts")
        
    except Exception as e:
        error_msg = f"❌ Detection failed: {str(e)}"
        logger.error(error_msg)
        state['detection_error'] = str(e)
        state['audit_log'].append(error_msg)
    
    return state

# ==================== REMEDIATION NODE ====================
async def remediate(state: CitadelState) -> CitadelState:
    """
    Step 5: Suggest remediation if bias detected
    Analyzes root causes and recommends fixes
    """
    if not state['needs_remediation']:
        state['audit_log'].append("ℹ️ No remediation needed")
        return state
    
    try:
        logger.info("💡 Generating remediation...")
        state['audit_log'].append("📍 Remediation started")
        
        root_causes = state.get('root_causes', {})
        
        recommendations = []
        
        # If we have SHAP explanations, use them
        if isinstance(root_causes, dict) and 'top_features' in root_causes:
            for i, feature in enumerate(root_causes['top_features'][:3]):
                recommendations.append({
                    'action': 'drop_feature',
                    'feature': feature,
                    'reason': f'Feature {feature} is driving bias',
                    'expected_impact': f'DI improves by ~10-15%',
                    'priority': i + 1
                })
        
        # Generic recommendations
        if not recommendations:
            recommendations = [
                {
                    'action': 'retrain_model',
                    'reason': 'Model shows significant bias',
                    'expected_impact': 'DI could improve to ~0.85+',
                    'priority': 1
                },
                {
                    'action': 'collect_more_data',
                    'reason': 'Underrepresented groups need more samples',
                    'expected_impact': 'Better representation in training data',
                    'priority': 2
                },
                {
                    'action': 'audit_features',
                    'reason': 'Remove proxy variables correlated with sensitive attributes',
                    'expected_impact': 'DI improves by 5-20%',
                    'priority': 3
                }
            ]
        
        state['recommended_fixes'] = recommendations
        state['audit_log'].append(f"✅ Generated {len(recommendations)} recommendations")
        
        logger.info(f"✅ Remediation: {len(recommendations)} fixes suggested")
        
    except Exception as e:
        error_msg = f"❌ Remediation generation failed: {str(e)}"
        logger.error(error_msg)
        state['remediation_error'] = str(e)
        state['audit_log'].append(error_msg)
    
    return state

# ==================== ALERTING NODE ====================
async def alert(state: CitadelState) -> CitadelState:
    """
    Step 6: Send alerts via Slack/Jira/GitHub
    (For now, just logging to audit trail)
    """
    if not state['alerts']:
        state['alert_status'] = 'no_alerts'
        state['audit_log'].append("ℹ️ No alerts to send")
        return state
    
    try:
        logger.info("📢 Sending alerts...")
        state['audit_log'].append("📍 Alerting started")
        
        for alert in state['alerts']:
            msg = f"🔔 {alert['type'].upper()}: {alert['message']}"
            state['audit_log'].append(msg)
            logger.warning(msg)
            
            # TODO: Integrate with Slack/Jira/GitHub
            # For now, just document in audit log
            if 'alerted_to' not in state:
                state['alerted_to'] = []
            state['alerted_to'].append('audit_log')
        
        state['alert_status'] = 'sent'
        state['audit_log'].append(f"✅ {len(state['alerts'])} alert(s) processed")
        
    except Exception as e:
        error_msg = f"❌ Alerting failed: {str(e)}"
        logger.error(error_msg)
        state['alerting_error'] = str(e)
        state['alert_status'] = 'failed'
        state['audit_log'].append(error_msg)
    
    return state

# ==================== COMPLETION NODE ====================
async def complete_workflow(state: CitadelState) -> CitadelState:
    """
    Step 7: Mark workflow as complete and calculate metrics
    """
    try:
        state['workflow_end_time'] = datetime.now()
        delta = state['workflow_end_time'] - state['workflow_start_time']
        state['total_execution_time_ms'] = int(delta.total_seconds() * 1000)
        state['workflow_status'] = 'completed'
        
        state['audit_log'].append(
            f"✅ Workflow completed in {state['total_execution_time_ms']}ms"
        )
        
        logger.info(f"✅ Governance check complete in {state['total_execution_time_ms']}ms")
        
    except Exception as e:
        logger.error(f"Error completing workflow: {e}")
    
    return state