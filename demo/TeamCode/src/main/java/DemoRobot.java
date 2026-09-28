public class DemoRobot {
    public static final String FEEDER_NAME = "feeder";

    public void initialize() {
        hardwareMap.get(DcMotorEx.class, "frontLeft");
        hardwareMap.get(DcMotorEx.class, "frontRight");
        hardwareMap.get(DcMotorEx.class, "backLeft");
        hardwareMap.get(DcMotorEx.class, "backRight");
        hardwareMap.get(DcMotorEx.class, "flywheel");
        hardwareMap.get(DcMotorEx.class, "intakeMotor");
        hardwareMap.get(DcMotorEx.class, "turret");
        hardwareMap.get(Servo.class, FEEDER_NAME);
        hardwareMap.get(Limelight3A.class, "limelight");
    }
}
