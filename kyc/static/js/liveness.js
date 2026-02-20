
        let video;
        let model;
        let detectionInterval;
        let isDetecting = false;
        let challenges = {
            center: false,
            left: false,
            right: false,
            mouth: false
        };
        let currentInstruction = 'center';
        const params = new URLSearchParams(window.location.search);
        const SESSION_ID = params.get("session_id");  // may be null if not passed
        console.log("Liveness SESSION_ID:", SESSION_ID);

        const instructions = {
            center: 'Look at the center',
            left: 'Turn your head LEFT ⬅️',
            right: 'Turn your head RIGHT ➡️',
            mouth: 'Open your MOUTH WIDE! 😮'
        };

        const instructionOrder = ['center', 'left', 'right', 'mouth'];

        async function init() {
            try {
                console.log('Starting initialization...');
                video = document.getElementById('video');

                console.log('Setting TensorFlow backend...');
                await tf.setBackend('webgl');
                await tf.ready();
                console.log('TensorFlow ready');

                console.log('Requesting camera access...');
                const stream = await getFrontCameraStream();

                video.srcObject = stream;

                await new Promise((resolve) => {
                    video.onloadedmetadata = () => {
                        video.play();
                        console.log('Video playing:', video.videoWidth, 'x', video.videoHeight);
                        resolve();
                    };
                });

                console.log('Loading face detection model...');
                model = await faceLandmarksDetection.createDetector(
                    faceLandmarksDetection.SupportedModels.MediaPipeFaceMesh,
                    {
                        runtime: 'mediapipe',
                        maxFaces: 1,
                        refineLandmarks: true,
                        solutionPath: 'https://cdn.jsdelivr.net/npm/@mediapipe/face_mesh'
                    }
                );
                console.log('Model loaded successfully');

                document.getElementById('loadingScreen').classList.add('hidden');
                document.getElementById('mainScreen').classList.remove('hidden');

                showStatus('info', 'Ready! Click "Start Liveness Check" to begin');

            } catch (error) {
                console.error('Init error:', error);
                const permissionState = await getCameraPermissionState();
                showStatus('error', getCameraErrorMessage(error, permissionState));
            }
        }

        async function getFrontCameraStream() {
            const constraints = [
                { audio: false, video: { facingMode: { exact: 'user' }, width: { ideal: 720 }, height: { ideal: 960 } } },
                { audio: false, video: { facingMode: { ideal: 'user' }, width: { ideal: 720 }, height: { ideal: 960 } } },
                { audio: false, video: { width: { ideal: 720 }, height: { ideal: 960 } } }
            ];

            let lastError = null;
            for (const config of constraints) {
                try {
                    return await navigator.mediaDevices.getUserMedia(config);
                } catch (error) {
                    lastError = error;
                }
            }

            throw lastError || new Error('Camera access failed');
        }

        async function startDetection() {
            document.getElementById('startBtn').disabled = true;
            showStatus('info', 'Starting liveness detection...');
            isDetecting = true;

            try {
                await fetch('/start-liveness/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
            } catch (e) {
                console.log('Backend notification failed:', e);
            }

            challenges = { center: false, left: false, right: false, mouth: false };
            currentInstruction = 'center';
            updateInstruction();

            if (detectionInterval) clearInterval(detectionInterval);

            detectionInterval = setInterval(detectFace, 300);
        }

        async function detectFace() {
            if (!model || !video || video.readyState !== 4 || !isDetecting) {
                return;
            }

            try {
                const predictions = await model.estimateFaces(video, {
                    flipHorizontal: false
                });

                if (predictions.length > 0) {
                    const face = predictions[0];
                    analyzeFace(face);
                    updateDebug(`Face detected | Keypoints: ${face.keypoints.length}`);
                } else {
                    updateDebug('No face detected');
                }
            } catch (error) {
                console.error('Detection error:', error);
                updateDebug(`Error: ${error.message}`);
            }
        }

        function analyzeFace(face) {
            const keypoints = face.keypoints;

            // Key facial landmarks
            const noseTip = keypoints[1];
            const leftEye = keypoints[33];
            const rightEye = keypoints[263];

            // Mouth landmarks for open mouth detection
            const upperLipTop = keypoints[13];      // Top of upper lip
            const lowerLipBottom = keypoints[14];   // Bottom of lower lip
            const leftMouth = keypoints[61];        // Left corner
            const rightMouth = keypoints[291];      // Right corner

            // Calculate face orientation
            const eyeCenter = {
                x: (leftEye.x + rightEye.x) / 2,
                y: (leftEye.y + rightEye.y) / 2
            };

            const faceAngle = Math.atan2(
                noseTip.y - eyeCenter.y,
                noseTip.x - eyeCenter.x
            );
            const faceTurn = (faceAngle * 180 / Math.PI) - 90;

            // ✅ Calculate mouth opening (vertical distance)
            const mouthHeight = Math.abs(lowerLipBottom.y - upperLipTop.y);
            const mouthWidth = Math.abs(rightMouth.x - leftMouth.x);

            // Calculate aspect ratio - open mouth has higher ratio
            const mouthAspectRatio = mouthHeight / mouthWidth;

            // Also calculate absolute opening distance for better detection
            const absoluteMouthOpening = mouthHeight;

            updateDebug(`Turn: ${faceTurn.toFixed(1)}° | Mouth: ${(mouthAspectRatio * 100).toFixed(1)}% | Opening: ${absoluteMouthOpening.toFixed(1)}px`);

            // Check challenges
            if (!challenges.center && Math.abs(faceTurn) < 15) {
                completeChallenge('center');
                currentInstruction = 'left';
            } else if (!challenges.left && challenges.center && faceTurn > 25) {
                completeChallenge('left');
                currentInstruction = 'right';
            } else if (!challenges.right && challenges.left && faceTurn < -25) {
                completeChallenge('right');
                currentInstruction = 'mouth';
            } else if (!challenges.mouth && challenges.right) {
                // ✅ Detect wide open mouth
                // Using both ratio and absolute distance for better accuracy
                const isWideOpen = (mouthAspectRatio > 0.5 && absoluteMouthOpening > 20) ||
                                   (mouthAspectRatio > 0.6) ||
                                   (absoluteMouthOpening > 30);

                if (isWideOpen) {
                    completeChallenge('mouth');
                    finishDetection();
                }
            }
        }

        function completeChallenge(challenge) {
            challenges[challenge] = true;
            const challengeEl = document.getElementById(`challenge-${challenge}`);
            if (challengeEl) challengeEl.classList.add('completed');
            updateInstruction();

            showStatus('success', `✓ ${challenge.toUpperCase()} completed!`);
            setTimeout(() => {
                if (isDetecting) {
                    showStatus('info', instructions[currentInstruction]);
                }
            }, 1000);
        }

        function updateInstruction() {
            const instructionEl = document.getElementById('instruction');
            const index = Math.max(0, instructionOrder.indexOf(currentInstruction));
            const stepText = `Step ${index + 1}/${instructionOrder.length}`;
            if (instructionEl) {
                instructionEl.textContent = `${stepText}: ${instructions[currentInstruction]}`;
            }
        }

        function updateDebug(text) {
            const debug = document.getElementById('debugInfo');
            debug.classList.remove('hidden');
            debug.textContent = text;
        }

        async function finishDetection() {
            isDetecting = false;
            clearInterval(detectionInterval);

            const completed = Object.values(challenges).filter(v => v).length;
            const confidence = (completed / 4) * 100;

            showStatus('success', `✅ Liveness verified! Confidence: ${confidence}%`);

            const result = {
                session_id: SESSION_ID,
                verified: confidence >= 75,
                confidence: confidence,
                challenges: challenges
            };

            // Release camera immediately so parent page can open selfie camera without lock conflicts.
            if (video && video.srcObject) {
                video.srcObject.getTracks().forEach(track => track.stop());
                video.srcObject = null;
            }

            if (window.opener) {
                window.opener.postMessage({ type: 'liveness_result', data: result }, '*');
            } else if (window.parent !== window) {
                window.parent.postMessage({ type: 'liveness_result', data: result }, '*');
            }

            setTimeout(() => {
                if (window.opener || window.parent !== window) {
                    window.close();
                } else {
                    document.getElementById('startBtn').disabled = false;
                    document.getElementById('startBtn').textContent = 'Start Again';
                    isDetecting = false;
                }
            }, 350);
        }

        function showStatus(type, message) {
            const status = document.getElementById('statusMessage');
            status.className = `status-message ${type}`;
            status.textContent = message;
        }

        async function getCameraPermissionState() {
            try {
                if (!navigator.permissions || !navigator.permissions.query) return null;
                const result = await navigator.permissions.query({ name: 'camera' });
                return result.state || null;
            } catch (_) {
                return null;
            }
        }

        function getCameraErrorMessage(error, permissionState = null) {
            if (!error) return 'Camera access failed.';
            if (!window.isSecureContext) return 'Camera requires HTTPS (or localhost).';
            if (error.name === 'NotAllowedError' || error.name === 'PermissionDeniedError') {
                if (permissionState === 'granted') return 'Camera is busy in another tab/window. Please close other camera pages and retry.';
                return 'Camera permission denied. Please allow camera access in browser settings.';
            }
            if (error.name === 'NotReadableError' || error.name === 'TrackStartError') return 'Camera is already in use by another application.';
            if (error.name === 'NotFoundError' || error.name === 'DevicesNotFoundError') return 'No camera found on this device.';
            if (error.name === 'OverconstrainedError' || error.name === 'ConstraintNotSatisfiedError') return 'Front camera is not available with current settings. Please retry.';
            return `Initialization failed: ${error.message || 'Unknown camera error.'}`;
        }

        window.addEventListener('load', init);

        window.addEventListener('beforeunload', () => {
            if (detectionInterval) clearInterval(detectionInterval);
            if (video && video.srcObject) {
                video.srcObject.getTracks().forEach(track => track.stop());
            }
        });

        window.addEventListener('pagehide', () => {
            if (detectionInterval) clearInterval(detectionInterval);
            if (video && video.srcObject) {
                video.srcObject.getTracks().forEach(track => track.stop());
                video.srcObject = null;
            }
        });
