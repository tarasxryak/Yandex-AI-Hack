import styles from "./RequestCard.module.css"
import clsx from "clsx"

type RequestCardProps = {
    request : string,
    time : string,
    isActive: boolean,
}

const RequestCard = ({request, time, isActive } : RequestCardProps) => {
    return (
        <>
            <div className={styles.timeWrapper}>
                <span className={styles.timeString}>{time}</span>
            </div>
            <button className={clsx(styles.requestField, isActive && styles.activeField)}>{request}</button>
        </>
    )
}

export default RequestCard;
