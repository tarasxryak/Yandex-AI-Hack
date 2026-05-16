import styles from "./RequestCard.module.css"
import clsx from "clsx"

type RequestCardProps = {
    request : string,
    time : string,
    isActive: boolean,
    onClick: () => void,
}

const RequestCard = ({request, time, isActive, onClick } : RequestCardProps) => {
    return (
        <>
            <div className={styles.timeWrapper}>
                <span className={styles.timeString}>{time}</span>
            </div>
            <button
                className={clsx(styles.requestField, isActive && styles.activeField)}
                type="button"
                onClick={onClick}
            >
                {request}
            </button>
        </>
    )
}

export default RequestCard;
