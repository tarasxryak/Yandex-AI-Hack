import styles from "./RequestCard.module.css"

type RequestCardProps = {
    request : string,
    time : string
}

const RequestCard = ({request, time } : RequestCardProps) => {
    return (
        <>
            <div className={styles.timeWrapper}>
                <span className={styles.timeString}>{time}</span>
            </div>
            <button className={styles.requestField}>{request}</button>
        </>
    )
}

export default RequestCard;
